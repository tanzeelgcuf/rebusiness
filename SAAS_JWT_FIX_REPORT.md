# Multi-Tenant SaaS — JWT & Integration Fix Report

**Date:** 2026-09-07
**Scope:** Phase 2 SaaS authentication & endpoint wiring
**Outcome:** All 34 integration tests passing ✅

---

## Summary

The Phase 2 multi-tenant SaaS layer was 95% complete but had three runtime bugs that
blocked every protected endpoint from authenticating. All three were diagnosed and
fixed, the sam_gov blueprint was wired into the app factory, and the full integration
test suite (`tests/test_saas_workflow.sh`) now passes 34/34.

---

## Bugs Fixed

### 1. `ImportError: cannot import name 'jwt_optional'`

**Symptom:**
```
ERROR:app:Tenant context extraction error: cannot import name 'jwt_optional'
File "/.../app/__init__.py", line 55, in tenant_context
    from flask_jwt_extended import jwt_optional, get_jwt_identity
```

**Root cause:** `flask-jwt-extended` v4 removed `jwt_optional`. The deprecated v3
function was still referenced in the tenant context middleware.

**Fix:** `app/__init__.py` — switched to the v4 API:
```python
# before
from flask_jwt_extended import jwt_optional, get_jwt_identity
verify_jwt_in_request(optional=True)
claims = get_jwt_identity()

# after
from flask_jwt_extended import verify_jwt_in_request, get_jwt
verify_jwt_in_request(optional=True)
claims = get_jwt()
```

### 2. `Subject must be a string` (JWT identity must be a string in v4)

**Symptom:**
```
ERROR:app:Tenant context extraction error: Subject must be a string
INFO:werkzeug: 401 Unauthorized on /api/v1/dashboard/stats
```

**Root cause:** `flask-jwt-extended` v4 enforces that the JWT `sub` claim (the value
passed as `identity`) must be a string. The signup / login / refresh code passed a
dict, which v4 rejects at decode time.

**Fix:** `app/api/v1/auth.py` — store tenant/user/role in `additional_claims` and
pass `str(user.id)` as the identity:
```python
# before
access_token = create_access_token(identity={
    'tenant_id': tenant.id, 'user_id': user.id, 'role': user.role
})

# after
additional_claims = {
    'tenant_id': tenant.id, 'user_id': user.id, 'role': user.role
}
access_token = create_access_token(
    identity=str(user.id),
    additional_claims=additional_claims
)
```

The same change was applied to `create_refresh_token` and the `/auth/refresh`
handler. Across the codebase, every `get_jwt_identity()` call was replaced with
`get_jwt()` (which returns the full claims dict, including `additional_claims`),
and `claims.get('user_id')` was used in place of subscripting a non-dict identity.

### 3. `sqlalchemy.exc.NoForeignKeysError` on `AutomationRun.audit_logs`

**Symptom:** `Could not determine join condition between parent/child tables on
relationship AutomationRun.audit_logs`.

**Root cause:** `AuditLog.resource_id` is a polymorphic FK (it can reference an
`automation_run`, an `rfq`, or a `vendor`), so SQLAlchemy can't auto-detect the
join condition. The `Tenant.audit_logs` relationship already filtered by
`tenant_id` correctly; the `AutomationRun.audit_logs` relationship needed an
explicit `primaryjoin` with a `foreign()` annotation.

**Fix:** `app/models/__init__.py`:
```python
# primaryjoin with foreign() annotation: AuditLog.resource_id is polymorphic
audit_logs = db.relationship(
    'AuditLog', backref='automation_run', lazy='dynamic', cascade='all, delete-orphan',
    primaryjoin="and_(AutomationRun.id == foreign(AuditLog.resource_id), "
    "             AuditLog.resource_type=='automation_run')"
)
```

### 4. AuditLog missing `user_id` column

**Symptom:** `TypeError: 'user_id' is an invalid keyword argument for AuditLog` on
every `AuditLog(...)` construction in `sam_gov.py`.

**Root cause:** `AuditLog` was modelled without a `user_id` column (user identity
lives on the JWT). The SAM.gov endpoints passed `user_id` directly to the
constructor.

**Fix:** `app/api/v1/sam_gov.py` — moved `user_id` into the JSON `details` field
on all five `AuditLog` instances (connect, disconnect, test, settings_updated,
sync_triggered).

### 5. `sam_gov` blueprint not registered

**Symptom:** `GET /api/v1/sam-gov/settings` returned 404 even though the route
existed in `app/api/v1/sam_gov.py`.

**Root cause:** `app/__init__.py` never imported or registered the `sam_gov`
blueprint. The blueprint self-declares `url_prefix='/api/v1/sam-gov'`, so the
fix was a single line in the factory.

**Fix:**
```python
from app.api.v1 import automation, dashboard, rfqs, vendors, auth, sam_gov
app.register_blueprint(sam_gov.sam_gov_bp)   # url_prefix already inside
```

### 6. Public health endpoint

**Symptom:** `/api/v1/health` returned 401 because the tenant middleware
auto-verifies every non-excluded path. The test script and external load
balancers expect a public health check.

**Fix:** Added `/api/v1/health` to the tenant-context bypass list and registered
a new route returning `{status: healthy, api_version: v1}`.

### 7. Refresh-token endpoint blocked by middleware

**Symptom:** `POST /api/v1/auth/refresh` failed with `Only non-refresh tokens are
allowed`. The middleware called `verify_jwt_in_request()` with default
behaviour (access token only) on a refresh-token endpoint.

**Fix:** Added `/api/v1/auth/refresh` to the middleware bypass list. The
`@jwt_required(refresh=True)` decorator on the endpoint itself handles the
refresh-token verification.

---

## Files Modified

| File | Change |
|---|---|
| `app/__init__.py` | v4 JWT API; bypass list; sam_gov blueprint registered; public `/api/v1/health` route |
| `app/api/v1/auth.py` | `additional_claims` pattern; all `get_jwt_identity()` → `get_jwt()` |
| `app/auth/tenant_auth.py` | `get_jwt_identity()` → `get_jwt()` |
| `app/api/v1/sam_gov.py` | Removed invalid `user_id=` from 5 `AuditLog` constructors |
| `app/api/v1/__init__.py` | Added `sam_gov` to imports |
| `app/models/__init__.py` | `AutomationRun.audit_logs` primaryjoin with `foreign()` annotation |
| `tests/test_saas_workflow.sh` | Pre-flight uses public `/health` instead of `/api/v1/health` |

---

## Verification

```
$ tests/test_saas_workflow.sh http://localhost:5002
...
Tests Run:    34
Tests Passed: 34
Tests Failed: 0
✓ All tests passed!
```

Coverage:
- Multi-tenant signup (3 tenants, no collisions)
- Login with valid / invalid credentials
- `/auth/me`, `/auth/refresh`, `/auth/logout`
- Cross-tenant data isolation (tenant A cannot see tenant B's data)
- All 6 SAM.gov endpoints (connect, disconnect, test, settings GET/PATCH, sync, sync-status, sync-history)
- Dashboard stats, automation history, recent runs
- RFQ and vendor list endpoints
- Authentication enforcement on protected endpoints

---

## Deployment Notes

- The Flask dev server runs on `PORT=5002` by default (port 5000 is occupied by
  macOS ControlCenter / AirPlay on dev machines).
- `app/__init__.py:14` (db, jwt init) requires `from app import db, jwt` — make
  sure the extension singletons are imported before any blueprint module that
  references them.
- `env -u PYTHONPATH` is required to start the server when the Anaconda Python
  is on the path, otherwise multiprocessing's `concurrent.futures` is shadowed
  by an incompatible system Python.
