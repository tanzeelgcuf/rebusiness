"""
Celery Task Definitions
Background job queue for automation workflows
"""

from celery import Celery, Task
from app import create_app, db
from app.models import AutomationRun
from app.orchestration.automation_controller import AutomationController
import logging

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(__name__)


class ContextTask(Task):
    """Celery task that runs within Flask app context"""
    def __call__(self, *args, **kwargs):
        app = create_app()
        with app.app_context():
            return self.run(*args, **kwargs)


celery_app.Task = ContextTask


def init_celery(app):
    """Initialize Celery with Flask app configuration"""
    celery_app.conf.update(app.config)

    # Task base name
    class ContextTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    return celery_app


@celery_app.task(
    name='automation.run_automation_workflow',
    bind=True,
    max_retries=1,
    time_limit=3600  # 1 hour hard limit
)
def run_automation_workflow(self, automation_run_id: int, tenant_id: int):
    """
    Master task: Execute complete RFQ automation workflow.

    Orchestrates:
    1. SAM.gov scraping
    2. RFQ generation
    3. Product extraction
    4. Vendor search
    5. RFQ submission

    Args:
        automation_run_id: ID of AutomationRun record
        tenant_id: Tenant ID for scoping

    Returns:
        Dict with workflow results
    """
    try:
        logger.info(
            f"Starting automation workflow task",
            extra={
                'task_id': self.request.id,
                'run_id': automation_run_id,
                'tenant_id': tenant_id
            }
        )

        # Initialize controller
        controller = AutomationController(automation_run_id, tenant_id)

        # Execute workflow
        result = controller.execute_workflow()

        logger.info(
            f"Automation workflow task completed",
            extra={
                'task_id': self.request.id,
                'run_id': automation_run_id,
                'status': result['status'],
                'errors': len(result['errors'])
            }
        )

        return result

    except Exception as exc:
        logger.error(
            f"Automation workflow task failed: {exc}",
            extra={
                'task_id': self.request.id,
                'run_id': automation_run_id,
                'tenant_id': tenant_id
            },
            exc_info=True
        )

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    name='automation.scrape_sam_gov',
    bind=True,
    max_retries=2,
    time_limit=1800  # 30 minutes
)
def scrape_sam_gov(self, automation_run_id: int, tenant_id: int):
    """
    Background task: Scrape SAM.gov solicitations.

    Args:
        automation_run_id: Parent AutomationRun ID
        tenant_id: Tenant ID

    Returns:
        Dict with scraping results
    """
    try:
        logger.info(
            f"Starting SAM.gov scraping task",
            extra={
                'task_id': self.request.id,
                'run_id': automation_run_id,
                'tenant_id': tenant_id
            }
        )

        # TODO: Integrate with actual SamGovAgent
        # For now, placeholder
        result = {'count': 5, 'status': 'success'}

        logger.info(
            f"SAM.gov scraping task completed",
            extra={
                'task_id': self.request.id,
                'run_id': automation_run_id,
                'count': result['count']
            }
        )

        return result

    except Exception as exc:
        logger.error(
            f"SAM.gov scraping task failed: {exc}",
            extra={
                'task_id': self.request.id,
                'run_id': automation_run_id
            },
            exc_info=True
        )
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(
    name='automation.generate_rfq',
    bind=True,
    max_retries=2,
    time_limit=1800  # 30 minutes
)
def generate_rfq(self, automation_run_id: int, tenant_id: int, contract_id: str):
    """
    Background task: Generate RFQ document for solicitation.

    Args:
        automation_run_id: Parent AutomationRun ID
        tenant_id: Tenant ID
        contract_id: SAM.gov contract ID

    Returns:
        Dict with generation results
    """
    try:
        logger.info(
            f"Starting RFQ generation task",
            extra={
                'task_id': self.request.id,
                'run_id': automation_run_id,
                'contract_id': contract_id
            }
        )

        # TODO: Integrate with actual AttachmentReaderAgent
        # For now, placeholder
        result = {'contract_id': contract_id, 'status': 'success'}

        logger.info(
            f"RFQ generation task completed",
            extra={
                'task_id': self.request.id,
                'contract_id': contract_id
            }
        )

        return result

    except Exception as exc:
        logger.error(
            f"RFQ generation task failed: {exc}",
            extra={
                'task_id': self.request.id,
                'contract_id': contract_id
            },
            exc_info=True
        )
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(
    name='automation.search_vendors',
    bind=True,
    max_retries=2,
    time_limit=1800  # 30 minutes
)
def search_vendors(self, automation_run_id: int, tenant_id: int, contract_id: str):
    """
    Background task: Search for vendors on ThomasNet.

    Args:
        automation_run_id: Parent AutomationRun ID
        tenant_id: Tenant ID
        contract_id: SAM.gov contract ID

    Returns:
        Dict with vendor search results
    """
    try:
        logger.info(
            f"Starting vendor search task",
            extra={
                'task_id': self.request.id,
                'run_id': automation_run_id,
                'contract_id': contract_id
            }
        )

        # TODO: Integrate with actual VendorSearchAgent + EmailExtractor
        # For now, placeholder
        result = {'contract_id': contract_id, 'vendors_found': 47, 'status': 'success'}

        logger.info(
            f"Vendor search task completed",
            extra={
                'task_id': self.request.id,
                'contract_id': contract_id,
                'vendors_found': result['vendors_found']
            }
        )

        return result

    except Exception as exc:
        logger.error(
            f"Vendor search task failed: {exc}",
            extra={
                'task_id': self.request.id,
                'contract_id': contract_id
            },
            exc_info=True
        )
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(
    name='automation.submit_rfq',
    bind=True,
    max_retries=1,
    time_limit=1800  # 30 minutes
)
def submit_rfq(self, automation_run_id: int, tenant_id: int, contract_id: str):
    """
    Background task: Submit RFQ to vendors.

    Args:
        automation_run_id: Parent AutomationRun ID
        tenant_id: Tenant ID
        contract_id: SAM.gov contract ID

    Returns:
        Dict with submission results
    """
    try:
        logger.info(
            f"Starting RFQ submission task",
            extra={
                'task_id': self.request.id,
                'run_id': automation_run_id,
                'contract_id': contract_id
            }
        )

        # TODO: Integrate with actual SubmissionAgent
        # For now, placeholder
        result = {'contract_id': contract_id, 'submissions_sent': 235, 'status': 'success'}

        logger.info(
            f"RFQ submission task completed",
            extra={
                'task_id': self.request.id,
                'contract_id': contract_id,
                'submissions_sent': result['submissions_sent']
            }
        )

        return result

    except Exception as exc:
        logger.error(
            f"RFQ submission task failed: {exc}",
            extra={
                'task_id': self.request.id,
                'contract_id': contract_id
            },
            exc_info=True
        )
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name='automation.health_check')
def health_check():
    """Periodic health check task"""
    logger.info("Celery health check completed")
    return {'status': 'healthy', 'timestamp': str(__import__('datetime').datetime.utcnow())}
