"""
Celery tasks for SAM.gov synchronization
"""

import logging
import time
from datetime import datetime, timedelta

import requests
from celery import shared_task

from app import create_app, db
from app.api.v1.sam_gov import decrypt_credential
from app.models import (
    SamGovCredentials,
    SamGovSyncHistory,
    Solicitation,
    AuditLog,
)

logger = logging.getLogger(__name__)

SAM_GOV_API_BASE = "https://api.sam.gov"
SAM_GOV_OPPS_V2 = "/opportunities/v2/search"

# Create Flask app context for Celery tasks
flask_app = create_app()


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def run_sam_gov_sync(self, sync_id: int, tenant_id: int, user_id: int):
    """
    Run SAM.gov solicitation sync in background.
    Fetches solicitations matching tenant's settings and stores them.
    """
    with flask_app.app_context():
        try:
            sync = SamGovSyncHistory.query.get(sync_id)
            if not sync:
                logger.error(f"Sync {sync_id} not found")
                return

            creds = SamGovCredentials.query.get(sync.credentials_id)
            if not creds:
                sync.status = 'failed'
                sync.error_message = 'Credentials not found'
                sync.sync_completed_at = datetime.utcnow()
                db.session.commit()
                return

            # Decrypt API key
            try:
                api_key = decrypt_credential(creds.api_key_encrypted)
            except Exception as e:
                logger.error(f"Decryption failed: {e}")
                sync.status = 'failed'
                sync.error_message = 'Failed to decrypt credentials'
                sync.sync_completed_at = datetime.utcnow()
                db.session.commit()
                return

            # Get tenant settings
            tenant = creds.tenant
            sync_settings = (tenant.settings or {}).get('sam_gov_sync', {})

            # Build query params
            params = {
                'api_key': api_key,
                'postedFrom': (datetime.utcnow() - timedelta(days=7)).strftime('%m/%d/%Y'),
                'postedTo': datetime.utcnow().strftime('%m/%d/%Y'),
                'limit': 100,
            }

            # Apply NAICS filter
            naics_codes = sync_settings.get('naics_codes', [])
            if naics_codes:
                params['ncode'] = ','.join(naics_codes)

            # Apply set-aside filter
            set_asides = sync_settings.get('set_aside_filter', [])
            if set_asides:
                params['typeOfSetAside'] = ','.join(set_asides)

            # Fetch from SAM.gov
            start = time.time()
            response = requests.get(
                f"{SAM_GOV_API_BASE}{SAM_GOV_OPPS_V2}",
                params=params,
                timeout=30,
            )
            latency_ms = int((time.time() - start) * 1000)

            # Update rate limit info from headers
            if 'X-RateLimit-Remaining' in response.headers:
                creds.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
            if 'X-RateLimit-Reset' in response.headers:
                creds.rate_limit_reset_at = datetime.fromtimestamp(
                    int(response.headers['X-RateLimit-Reset'])
                )

            if response.status_code == 429:
                creds.connection_status = 'rate_limited'
                sync.status = 'failed'
                sync.error_message = 'SAM.gov rate limit exceeded'
                sync.sync_completed_at = datetime.utcnow()
                sync.duration_ms = latency_ms
                db.session.commit()
                return

            if response.status_code != 200:
                creds.connection_status = 'error'
                sync.status = 'failed'
                sync.error_message = f'SAM.gov API returned {response.status_code}: {response.text[:200]}'
                sync.sync_completed_at = datetime.utcnow()
                sync.duration_ms = latency_ms
                db.session.commit()
                return

            data = response.json()
            opps_data = data.get('opportunitiesData', [])

            # Apply keyword filter (client-side)
            keywords = [k.lower() for k in sync_settings.get('keywords', [])]
            if keywords:
                opps_data = [
                    opp for opp in opps_data
                    if any(kw in (opp.get('title', '') + ' ' + opp.get('description', '')).lower()
                           for kw in keywords)
                ]

            # Apply value filter
            min_val = sync_settings.get('min_value')
            max_val = sync_settings.get('max_value')
            if min_val or max_val:
                filtered = []
                for opp in opps_data:
                    award = opp.get('award', {})
                    try:
                        val = float(award.get('amount', 0) or 0)
                        if min_val and val < min_val:
                            continue
                        if max_val and val > max_val:
                            continue
                        filtered.append(opp)
                    except (ValueError, TypeError):
                        continue
                opps_data = filtered

            # Store solicitations
            saved_count = 0
            for opp in opps_data:
                solicitation_id = opp.get('solicitationNumber') or opp.get('noticeId')
                if not solicitation_id:
                    continue

                # Upsert
                existing = Solicitation.query.filter_by(
                    tenant_id=tenant_id,
                    contract_id=solicitation_id,
                ).first()

                if existing:
                    # Update
                    existing.title = opp.get('title', existing.title)
                    existing.description = opp.get('description', existing.description)
                    existing.data = opp
                else:
                    # Create new
                    solicitation = Solicitation(
                        tenant_id=tenant_id,
                        contract_id=solicitation_id,
                        url=opp.get('uiLink', ''),
                        title=opp.get('title', ''),
                        description=opp.get('description', ''),
                        location=opp.get('officeAddress', {}).get('city', ''),
                        data=opp,
                        review_status='pending',
                    )
                    db.session.add(solicitation)
                saved_count += 1

            # Update sync record
            sync.status = 'success'
            sync.solicitations_fetched = saved_count
            sync.sync_completed_at = datetime.utcnow()
            sync.duration_ms = latency_ms

            # Update credentials
            creds.last_sync_at = datetime.utcnow()
            creds.sync_count = (creds.sync_count or 0) + 1
            creds.connection_status = 'connected'

            # Audit log
            audit = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action='sam_gov_sync_completed',
                resource_type='sam_gov_sync',
                resource_id=str(sync_id),
                details={
                    'solicitations_fetched': saved_count,
                    'duration_ms': latency_ms,
                },
            )
            db.session.add(audit)

            db.session.commit()

            logger.info(
                f"SAM.gov sync {sync_id} completed: {saved_count} solicitations in {latency_ms}ms",
                extra={'tenant_id': tenant_id, 'sync_id': sync_id},
            )

        except requests.Timeout:
            logger.error(f"SAM.gov sync {sync_id} timed out")
            sync.status = 'failed'
            sync.error_message = 'Request to SAM.gov timed out'
            sync.sync_completed_at = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            logger.error(f"SAM.gov sync {sync_id} failed: {e}", exc_info=True)
            db.session.rollback()
            try:
                sync = SamGovSyncHistory.query.get(sync_id)
                if sync:
                    sync.status = 'failed'
                    sync.error_message = str(e)[:500]
                    sync.sync_completed_at = datetime.utcnow()
                    db.session.commit()
            except Exception:
                pass
            raise self.retry(exc=e, countdown=60)


def run_sam_gov_sync_sync(sync_id: int, tenant_id: int, user_id: int):
    """Synchronous fallback when Celery is unavailable (dev only)."""
    return run_sam_gov_sync.apply(args=[sync_id, tenant_id, user_id]).get()
