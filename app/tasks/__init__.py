"""
Tasks Module Package
Background job definitions and Celery configuration
"""

from app.tasks.automation_tasks import celery_app

__all__ = ['celery_app']
