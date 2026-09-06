"""
SAM.gov Integration API
Tenant-scoped SAM.gov account connection with credential management.

Endpoints:
- POST   /api/v1/sam-gov/connect        - Connect SAM.gov account (store credentials)
- POST   /api/v1/sam-gov/disconnect     - Disconnect and clear credentials
- POST   /api/v1/sam-gov/test           - Test stored credentials against SAM.gov API
- GET    /api/v1/sam-gov/settings       - Get current connection status (no secrets)
- PATCH  /api/v1/sam-gov/settings       - Update polling/sync settings
- POST   /api/v1/sam-gov/sync           - Trigger manual sync
- GET    /api/v1/sam-gov/sync-status    - Get current sync status
- GET    /api/v1/sam-gov/sync-history   - List past syncs
"""

import base64
import logging
import re
import secrets
import time
from datetime import datetime, timedelta

import requests
from cryptography.fernet import Fernet
from flask import Blueprint, current_app, g, jsonify, request

from app import db
from app.auth.tenant_auth import tenant_required
from app.models import AuditLog, SamGovCredentials, SamGovSyncHistory, Tenant

logger = logging.getLogger(__name__)

sam_gov_bp = Blueprint('sam_gov', __name__, url_prefix='/api/v1/sam-gov')

# =============================================================================
# SAM.gov API Constants
# =============================================================================
SAM_GOV_API_BASE = "https://api.sam.gov"
SAM_GOV_OPPS_V2 = "/opportunities/v2/search"
SAM_GOV_TEST_ENDPOINT = "/opportunities/v2/search"  # Same endpoint, can test with date filter

# Rate limiting per tenant
RATE_LIMIT_WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 10

# =============================================================================
# Encryption Helpers
# =============================================================================


def _get_encryption_key() -> bytes:
    """
    Get or generate the encryption key for SAM.gov credentials.
    In production, this MUST come from a secure key management system
    (AWS KMS, Google Secret Manager, HashiCorp Vault, etc.).
    """
    key = current_app.config.get('SAM_GOV_ENCRYPTION_KEY')
    if not key:
        # Generate a derived key from SECRET_KEY (NOT for production!)
        import hashlib
        secret = current_app.config.get('SECRET_KEY', 'dev-secret').encode()
        key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
        logger.warning(
            "Using derived encryption key for SAM.gov credentials. "
            "Set SAM_GOV_ENCRYPTION_KEY in production!"
        )
    elif isinstance(key, str):
        key = key.encode()
    return key


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a credential using Fernet (AES-128 in CBC mode + HMAC)."""
    f = Fernet(_get_encryption_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a credential."""
    f = Fernet(_get_encryption_key())
    return f.decrypt(ciphertext.encode()).decode()


# =============================================================================
# Validation Helpers
# =============================================================================


def validate_api_key(api_key: str) -> str:
    """
    Validate SAM.gov API key format.
    Returns error message if invalid, empty string if valid.
    """
    if not api_key:
        return "API key is required"
    if len(api_key) < 32:
        return "API key appears too short (SAM.gov keys are 32+ characters)"
    if len(api_key) > 256:
        return "API key is too long"
    return ""


def validate_entity_id(entity_id: str) -> str:
    """
    Validate SAM.gov Entity ID (UEI) format.
    Returns error message if invalid, empty string if valid.
    """
    if not entity_id:
        return "Entity ID is required"
    # UEI is 12 characters, alphanumeric
    if not re.match(r'^[A-Z0-9]{12}$', entity_id.upper()):
        return "Entity ID must be 12 alphanumeric characters (UEI format)"
    return ""


# =============================================================================
# Rate Limiting
# =============================================================================

_rate_limit_store = {}  # {tenant_id: [timestamps]}


def _check_rate_limit(tenant_id: int, max_requests: int = MAX_REQUESTS_PER_WINDOW) -> bool:
    """Check if tenant is within rate limit. Returns True if allowed."""
    now = time.time()
    if tenant_id not in _rate_limit_store:
        _rate_limit_store[tenant_id] = []

    # Prune old timestamps
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    _rate_limit_store[tenant_id] = [
        t for t in _rate_limit_store[tenant_id] if t > cutoff
    ]

    if len(_rate_limit_store[tenant_id]) >= max_requests:
        return False

    _rate_limit_store[tenant_id].append(now)
    return True


# ==========================================================================================
# 1. POST /api/v1/sam-gov/connect - Connect SAM.gov account
# ==========================================================================================
@sam_gov_bp.route('/connect', methods=['POST'])
@tenant_required
def connect_sam_gov():
    """
    Connect tenant to SAM.gov with API key + Entity ID.

    Body:
    {
        "api_key": "32+ char SAM.gov API key",
        "entity_id": "12-char UEI",
        "test_connection": true  // Optional: test before saving
    }
    """
    try:
        data = request.get_json() or {}
        api_key = (data.get('api_key') or '').strip()
        entity_id = (data.get('entity_id') or '').strip().upper()
        test_first = data.get('test_connection', True)

        # Validate
        api_key_error = validate_api_key(api_key)
        if api_key_error:
            return jsonify({'error': api_key_error, 'field': 'api_key'}), 400

        entity_id_error = validate_entity_id(entity_id)
        if entity_id_error:
            return jsonify({'error': entity_id_error, 'field': 'entity_id'}), 400

        # Rate limit
        if not _check_rate_limit(g.tenant_id):
            return jsonify({
                'error': 'Rate limit exceeded. Please wait before trying again.'
            }), 429

        # Optionally test credentials before saving
        if test_first:
            test_result = _test_sam_gov_credentials(api_key, entity_id)
            if not test_result['success']:
                return jsonify({
                    'error': f"Connection test failed: {test_result['error']}",
                    'test_result': test_result
                }), 400

        # Encrypt and store
        encrypted_key = encrypt_credential(api_key)
        last4 = api_key[-4:] if len(api_key) >= 4 else '****'

        # Upsert credentials
        creds = SamGovCredentials.query.filter_by(tenant_id=g.tenant_id).first()
        if creds:
            creds.api_key_encrypted = encrypted_key
            creds.entity_id = entity_id
            creds.api_key_last4 = last4
            creds.connection_status = 'connected'
            creds.last_test_at = datetime.utcnow()
            creds.last_test_success = True
            creds.last_test_error = None
            creds.updated_at = datetime.utcnow()
        else:
            creds = SamGovCredentials(
                tenant_id=g.tenant_id,
                api_key_encrypted=encrypted_key,
                entity_id=entity_id,
                api_key_last4=last4,
                connection_status='connected',
                last_test_at=datetime.utcnow(),
                last_test_success=True,
            )
            db.session.add(creds)

        # Audit log
        audit = AuditLog(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            action='sam_gov_connected',
            resource_type='sam_gov_credentials',
            resource_id=str(creds.id),
            details={
                'entity_id': entity_id,
                'api_key_last4': last4,
                'tested': test_first,
            }
        )
        db.session.add(audit)
        db.session.commit()

        logger.info(
            f"SAM.gov connected for tenant {g.tenant_id}",
            extra={'tenant_id': g.tenant_id, 'user_id': g.user_id}
        )

        return jsonify({
            'success': True,
            'message': 'SAM.gov account connected successfully',
            'credentials': {
                'entity_id': entity_id,
                'api_key_last4': last4,
                'connection_status': 'connected',
                'last_test_at': creds.last_test_at.isoformat() if creds.last_test_at else None,
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"SAM.gov connect error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to connect SAM.gov account'}), 500


# ==========================================================================================
# 2. POST /api/v1/sam-gov/disconnect
# ==========================================================================================
@sam_gov_bp.route('/disconnect', methods=['POST'])
@tenant_required
def disconnect_sam_gov():
    """Disconnect and remove SAM.gov credentials."""
    try:
        creds = SamGovCredentials.query.filter_by(tenant_id=g.tenant_id).first()
        if not creds:
            return jsonify({'error': 'No SAM.gov connection found'}), 404

        # Audit log (before deletion)
        audit = AuditLog(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            action='sam_gov_disconnected',
            resource_type='sam_gov_credentials',
            resource_id=str(creds.id),
            details={'entity_id': creds.entity_id}
        )
        db.session.add(audit)

        db.session.delete(creds)
        db.session.commit()

        logger.info(
            f"SAM.gov disconnected for tenant {g.tenant_id}",
            extra={'tenant_id': g.tenant_id, 'user_id': g.user_id}
        )

        return jsonify({
            'success': True,
            'message': 'SAM.gov account disconnected'
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"SAM.gov disconnect error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to disconnect'}), 500


# ==========================================================================================
# 3. POST /api/v1/sam-gov/test - Test credentials
# ==========================================================================================
@sam_gov_bp.route('/test', methods=['POST'])
@tenant_required
def test_sam_gov():
    """
    Test stored SAM.gov credentials.

    Optionally accepts new credentials in body to test without saving.
    """
    try:
        data = request.get_json() or {}

        # If credentials provided in body, test those; otherwise use stored
        if data.get('api_key') and data.get('entity_id'):
            api_key = data['api_key'].strip()
            entity_id = data['entity_id'].strip().upper()
        else:
            creds = SamGovCredentials.query.filter_by(tenant_id=g.tenant_id).first()
            if not creds:
                return jsonify({
                    'error': 'No SAM.gov connection found. Connect first.'
                }), 404
            api_key = decrypt_credential(creds.api_key_encrypted)
            entity_id = creds.entity_id

        # Rate limit
        if not _check_rate_limit(g.tenant_id):
            return jsonify({'error': 'Rate limit exceeded'}), 429

        # Test against SAM.gov API
        result = _test_sam_gov_credentials(api_key, entity_id)

        # Update stored test result if using stored credentials
        if not (data.get('api_key') and data.get('entity_id')):
            creds = SamGovCredentials.query.filter_by(tenant_id=g.tenant_id).first()
            if creds:
                creds.last_test_at = datetime.utcnow()
                creds.last_test_success = result['success']
                creds.last_test_error = result.get('error')
                if not result['success']:
                    creds.connection_status = 'error'
                db.session.commit()

        # Audit
        audit = AuditLog(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            action='sam_gov_test',
            resource_type='sam_gov_credentials',
            details={'success': result['success'], 'latency_ms': result.get('latency_ms')}
        )
        db.session.add(audit)
        db.session.commit()

        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"SAM.gov test error: {e}", exc_info=True)
        return jsonify({'error': 'Test failed'}), 500


def _test_sam_gov_credentials(api_key: str, entity_id: str) -> dict:
    """
    Test SAM.gov credentials by making a minimal API call.
    Returns dict with success status, error message, and latency.
    """
    start = time.time()

    try:
        # SAM.gov v2 API requires date range - use yesterday to today
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%m/%d/%Y')
        today = datetime.utcnow().strftime('%m/%d/%Y')

        params = {
            'api_key': api_key,
            'postedFrom': yesterday,
            'postedTo': today,
            'limit': 1,
        }
        headers = {'Accept': 'application/json'}

        response = requests.get(
            f"{SAM_GOV_API_BASE}{SAM_GOV_TEST_ENDPOINT}",
            params=params,
            headers=headers,
            timeout=15
        )

        latency_ms = int((time.time() - start) * 1000)

        if response.status_code == 200:
            return {
                'success': True,
                'message': 'Connection successful',
                'latency_ms': latency_ms,
                'api_version': 'v2',
            }
        elif response.status_code == 401:
            return {
                'success': False,
                'error': 'Invalid API key',
                'latency_ms': latency_ms,
                'http_status': 401,
            }
        elif response.status_code == 403:
            return {
                'success': False,
                'error': 'API key lacks required permissions',
                'latency_ms': latency_ms,
                'http_status': 403,
            }
        elif response.status_code == 429:
            return {
                'success': False,
                'error': 'SAM.gov rate limit exceeded',
                'latency_ms': latency_ms,
                'http_status': 429,
            }
        else:
            error_body = response.text[:200] if response.text else 'Unknown error'
            return {
                'success': False,
                'error': f'SAM.gov API returned {response.status_code}: {error_body}',
                'latency_ms': latency_ms,
                'http_status': response.status_code,
            }

    except requests.Timeout:
        return {
            'success': False,
            'error': 'Connection to SAM.gov timed out (15s)',
            'latency_ms': int((time.time() - start) * 1000),
        }
    except requests.ConnectionError as e:
        return {
            'success': False,
            'error': f'Could not connect to SAM.gov: {str(e)[:200]}',
            'latency_ms': int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)[:200]}',
            'latency_ms': int((time.time() - start) * 1000),
        }


# ==========================================================================================
# 4. GET /api/v1/sam-gov/settings - Get current settings (no secrets)
# ==========================================================================================
@sam_gov_bp.route('/settings', methods=['GET'])
@tenant_required
def get_settings():
    """Get current SAM.gov connection status (no API key exposed)."""
    try:
        creds = SamGovCredentials.query.filter_by(tenant_id=g.tenant_id).first()
        tenant = Tenant.query.get(g.tenant_id)

        if not creds:
            return jsonify({
                'connected': False,
                'message': 'No SAM.gov connection configured',
                'sync_settings': {
                    'auto_sync_enabled': False,
                    'sync_interval_hours': 24,
                    'naics_codes': [],
                }
            }), 200

        # Get sync settings from tenant settings JSON
        sync_settings = (tenant.settings or {}).get('sam_gov_sync', {})

        return jsonify({
            'connected': True,
            'connection_status': creds.connection_status,
            'credentials': {
                'entity_id': creds.entity_id,
                'api_key_last4': creds.api_key_last4,
                'last_test_at': creds.last_test_at.isoformat() if creds.last_test_at else None,
                'last_test_success': creds.last_test_success,
                'last_test_error': creds.last_test_error if not creds.last_test_success else None,
                'last_sync_at': creds.last_sync_at.isoformat() if creds.last_sync_at else None,
                'sync_count': creds.sync_count,
                'rate_limit_remaining': creds.rate_limit_remaining,
                'rate_limit_reset_at': creds.rate_limit_reset_at.isoformat() if creds.rate_limit_reset_at else None,
            },
            'sync_settings': {
                'auto_sync_enabled': sync_settings.get('auto_sync_enabled', False),
                'sync_interval_hours': sync_settings.get('sync_interval_hours', 24),
                'naics_codes': sync_settings.get('naics_codes', []),
                'keywords': sync_settings.get('keywords', []),
                'min_value': sync_settings.get('min_value'),
                'max_value': sync_settings.get('max_value'),
                'set_aside_filter': sync_settings.get('set_aside_filter', []),
            },
        }), 200

    except Exception as e:
        logger.error(f"Get settings error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load settings'}), 500


# ==========================================================================================
# 5. PATCH /api/v1/sam-gov/settings - Update sync settings
# ==========================================================================================
@sam_gov_bp.route('/settings', methods=['PATCH'])
@tenant_required
def update_settings():
    """
    Update sync settings (no credentials change here).

    Body:
    {
        "auto_sync_enabled": true,
        "sync_interval_hours": 12,
        "naics_codes": ["334111", "511210"],
        "keywords": ["procurement", "supplies"],
        "min_value": 10000,
        "max_value": 1000000,
        "set_aside_filter": ["SBA", "8A"]
    }
    """
    try:
        data = request.get_json() or {}

        # Validate
        if 'sync_interval_hours' in data:
            interval = data['sync_interval_hours']
            if not isinstance(interval, int) or interval < 1 or interval > 168:
                return jsonify({
                    'error': 'sync_interval_hours must be 1-168 (1 hour to 1 week)'
                }), 400

        if 'naics_codes' in data:
            codes = data['naics_codes']
            if not isinstance(codes, list):
                return jsonify({'error': 'naics_codes must be a list'}), 400
            for code in codes:
                if not re.match(r'^\d{6}$', str(code)):
                    return jsonify({
                        'error': f'Invalid NAICS code: {code} (must be 6 digits)'
                    }), 400

        # Update tenant settings
        tenant = Tenant.query.get(g.tenant_id)
        if not tenant.settings:
            tenant.settings = {}

        sam_gov_settings = tenant.settings.get('sam_gov_sync', {})
        for key in ['auto_sync_enabled', 'sync_interval_hours', 'naics_codes',
                    'keywords', 'min_value', 'max_value', 'set_aside_filter']:
            if key in data:
                sam_gov_settings[key] = data[key]

        tenant.settings = {**tenant.settings, 'sam_gov_sync': sam_gov_settings}

        # Audit
        audit = AuditLog(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            action='sam_gov_settings_updated',
            resource_type='tenant',
            resource_id=str(g.tenant_id),
            details=sam_gov_settings,
        )
        db.session.add(audit)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Settings updated',
            'sync_settings': sam_gov_settings,
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Update settings error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update settings'}), 500


# ==========================================================================================
# 6. POST /api/v1/sam-gov/sync - Trigger manual sync
# ==========================================================================================
@sam_gov_bp.route('/sync', methods=['POST'])
@tenant_required
def trigger_sync():
    """
    Manually trigger a SAM.gov solicitation sync.
    Records start, returns immediately with sync_id (sync runs in background).
    """
    try:
        # Verify credentials exist
        creds = SamGovCredentials.query.filter_by(tenant_id=g.tenant_id).first()
        if not creds:
            return jsonify({
                'error': 'No SAM.gov connection. Connect your account first.'
            }), 400

        if creds.connection_status == 'error':
            return jsonify({
                'error': 'SAM.gov connection is in error state. Please test connection.'
            }), 400

        # Rate limit: max 1 manual sync per 5 minutes
        recent = SamGovSyncHistory.query.filter_by(
            tenant_id=g.tenant_id
        ).filter(
            SamGovSyncHistory.sync_started_at > datetime.utcnow() - timedelta(minutes=5)
        ).first()

        if recent and recent.status == 'running':
            return jsonify({
                'error': 'A sync is already in progress',
                'sync_id': recent.id,
            }), 409

        if recent and recent.status in ('pending', 'success'):
            return jsonify({
                'error': 'Please wait 5 minutes between manual syncs',
                'last_sync': recent.sync_started_at.isoformat(),
            }), 429

        # Create sync record
        sync = SamGovSyncHistory(
            tenant_id=g.tenant_id,
            credentials_id=creds.id,
            status='running',
            sync_started_at=datetime.utcnow(),
        )
        db.session.add(sync)
        creds.connection_status = 'syncing'
        db.session.commit()

        # Queue Celery task (lazy import to avoid circular deps)
        try:
            from app.tasks.sam_gov_tasks import run_sam_gov_sync
            run_sam_gov_sync.delay(sync.id, g.tenant_id, g.user_id)
        except ImportError:
            logger.warning("Celery task not available, running sync synchronously")
            # Fallback: synchronous (for dev)
            from app.tasks.sam_gov_tasks import run_sam_gov_sync_sync
            run_sam_gov_sync_sync(sync.id, g.tenant_id, g.user_id)

        # Audit
        audit = AuditLog(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            action='sam_gov_sync_triggered',
            resource_type='sam_gov_sync',
            resource_id=str(sync.id),
        )
        db.session.add(audit)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Sync started in background',
            'sync_id': sync.id,
        }), 202

    except Exception as e:
        db.session.rollback()
        logger.error(f"Trigger sync error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to trigger sync'}), 500


# ==========================================================================================
# 7. GET /api/v1/sam-gov/sync-status - Get current sync status
# ==========================================================================================
@sam_gov_bp.route('/sync-status', methods=['GET'])
@tenant_required
def get_sync_status():
    """Get status of most recent sync (in progress or last completed)."""
    try:
        # Get most recent sync
        latest = SamGovSyncHistory.query.filter_by(
            tenant_id=g.tenant_id
        ).order_by(SamGovSyncHistory.sync_started_at.desc()).first()

        if not latest:
            return jsonify({
                'has_sync': False,
                'message': 'No syncs yet',
            }), 200

        # Check if there's a running one
        running = SamGovSyncHistory.query.filter_by(
            tenant_id=g.tenant_id,
            status='running'
        ).order_by(SamGovSyncHistory.sync_started_at.desc()).first()

        current = running or latest

        return jsonify({
            'has_sync': True,
            'sync': {
                'id': current.id,
                'status': current.status,
                'started_at': current.sync_started_at.isoformat(),
                'completed_at': current.sync_completed_at.isoformat() if current.sync_completed_at else None,
                'duration_ms': current.duration_ms,
                'solicitations_fetched': current.solicitations_fetched,
                'error_message': current.error_message,
            }
        }), 200

    except Exception as e:
        logger.error(f"Get sync status error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load sync status'}), 500


# ==========================================================================================
# 8. GET /api/v1/sam-gov/sync-history - List past syncs
# ==========================================================================================
@sam_gov_bp.route('/sync-history', methods=['GET'])
@tenant_required
def get_sync_history():
    """Get paginated history of past syncs."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)

        query = SamGovSyncHistory.query.filter_by(tenant_id=g.tenant_id)
        total = query.count()
        syncs = query.order_by(
            SamGovSyncHistory.sync_started_at.desc()
        ).offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page,
            'syncs': [{
                'id': s.id,
                'status': s.status,
                'started_at': s.sync_started_at.isoformat(),
                'completed_at': s.sync_completed_at.isoformat() if s.sync_completed_at else None,
                'duration_ms': s.duration_ms,
                'solicitations_fetched': s.solicitations_fetched,
                'error_message': s.error_message,
            } for s in syncs]
        }), 200

    except Exception as e:
        logger.error(f"Get sync history error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load history'}), 500


# ==========================================================================================
# Helper for adapters.py - get decrypted credentials for a tenant
# ==========================================================================================

def get_tenant_sam_gov_credentials(tenant_id: int) -> dict:
    """
    Internal helper used by SamGovAgentAdapter.
    Returns dict with api_key and entity_id (decrypted), or None.
    """
    creds = SamGovCredentials.query.filter_by(tenant_id=tenant_id).first()
    if not creds or creds.connection_status != 'connected':
        return None
    try:
        return {
            'api_key': decrypt_credential(creds.api_key_encrypted),
            'entity_id': creds.entity_id,
            'credentials_id': creds.id,
        }
    except Exception as e:
        logger.error(f"Failed to decrypt SAM.gov credentials for tenant {tenant_id}: {e}")
        return None
