#!/usr/bin/env python
"""
Celery Worker Entry Point
Background job processor for RFQ automation
"""

import os
import logging
from app import create_app
from app.tasks.automation_tasks import celery_app, init_celery

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app and initialize Celery
app = create_app(config_name=os.getenv('FLASK_ENV', 'development'))
init_celery(app)

if __name__ == '__main__':
    logger.info("Starting Celery worker...")
    logger.info(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
    logger.info(f"Broker: {celery_app.conf.get('broker_url', 'N/A')}")
    logger.info(f"Result Backend: {celery_app.conf.get('result_backend', 'N/A')}")

    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--max-tasks-per-child=1000'
    ])
