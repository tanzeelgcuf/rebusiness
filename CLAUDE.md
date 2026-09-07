# ReBusiness Automation Project — Claude Code Notes

## Quick Start

```bash
# Start dev server (port 5000 is occupied by macOS AirPlay on dev machines)
env -u PYTHONPATH PORT=5002 .venv/bin/python run.py

# Run E2E test suite
./tests/test_saas_workflow.sh http://localhost:5002
```

`env -u PYTHONPATH` is required if the user's shell has Anaconda on PATH —
the Anaconda `concurrent.futures` shadows the venv copy and breaks
`threading`.

## Multi-Tenant SaaS Architecture

- `app/__init__.py` — Flask factory, tenant context middleware, error handlers
- `app/api/v1/auth.py` — signup, login, refresh, logout, /me
- `app/api/v1/dashboard.py` — stats, recent runs
- `app/api/v1/automation.py` — start, status, logs, history
- `app/api/v1/rfqs.py`, `vendors.py` — paginated list endpoints
- `app/api/v1/sam_gov.py` — 6 SAM.gov endpoints (connect, disconnect, test, settings GET/PATCH, sync, sync-status, sync-history)
- `app/models/__init__.py` — Tenant, User, AutomationRun, AgentLoopLog, AuditLog, Solicitation, RFQOutput, Vendor, SamGovCredentials, SamGovSyncHistory
- `app/auth/tenant_auth.py` — `@tenant_required`, `@admin_required` decorators
- `app/orchestration/` — agent loop with retry + backoff
- `app/tasks/` — Celery tasks (automation, sam_gov)

## JWT (flask-jwt-extended v4)

- Identity (`sub` claim) MUST be a string. Tenant/user/role go in `additional_claims`.
- Use `get_jwt()` (full claims dict) NOT `get_jwt_identity()` (returns just the
  string `sub`).
- `verify_jwt_in_request(optional=True)` replaces the v3 `jwt_optional()`.
- Refresh tokens use `@jwt_required(refresh=True)` and `/api/v1/auth/refresh`
  is excluded from the tenant-context middleware bypass list.

## Tenant Context Middleware

- `app/__init__.py:before_request` extracts `tenant_id` / `user_id` / `role` from
  the JWT and stashes them in `flask.g` so every endpoint handler can use them.
- Bypass list (no auth required): `/api/v1/auth/{login,signup,refresh}`,
  `/health`, `/api/v1/health`.
- For protected endpoints, queries must filter by `g.tenant_id`.

## AuditLog Polymorphic FK

`AuditLog.resource_id` references multiple parent tables (automation_run, rfq,
vendor). When defining a `relationship` from a parent table to `AuditLog`, you
MUST specify a `primaryjoin` with the `foreign()` annotation:

```python
audit_logs = db.relationship(
    'AuditLog', backref='automation_run', lazy='dynamic',
    primaryjoin="and_(AutomationRun.id == foreign(AuditLog.resource_id), "
    "             AuditLog.resource_type=='automation_run')"
)
```

`AuditLog` has no `user_id` column — store it in the `details` JSON field.

## Ports

- 5000 — macOS ControlCenter / AirPlay (cannot be used)
- 5001, 5002 — used during dev for Flask
- 6379 — Redis (Celery broker, when running workers)

## Phase Status

- Phase 1 (Core multi-tenancy): ✅ done
- Phase 2A (Dashboard UI): ✅ done
- Phase 2B (Production deploy: Dockerfile, docker-compose, nginx, postgres_schema): ✅ done
- Phase 2C (SAM.gov integration): ✅ done
- Phase 2D (Test script + CI/CD): ✅ done
- Phase 2E (Bug fixes — JWT v4, polymorphic FK, audit log): ✅ done (see `SAAS_JWT_FIX_REPORT.md`)

## Test Credentials (dev only)

```bash
curl -X POST http://localhost:5002/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "demo",
    "tenant_name": "Demo Co",
    "email": "admin@demo.com",
    "password": "SecurePass123!",
    "full_name": "Demo User"
  }'
```

The first user for a tenant is created with `role=admin`.
