"""
Agent Loop Orchestration Engine
Manages agent execution with automatic retry, exponential backoff, and detailed logging
"""

from datetime import datetime, timedelta
import time
import logging
from typing import Dict, Any, Optional
from app import db
from app.models import AutomationRun, AgentLoopLog, Tenant

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    Manages execution of individual agents with retry logic and logging.

    Features:
    - Automatic retry with exponential backoff
    - Per-subscription-tier retry limits
    - Detailed agent logging and status tracking
    - Error handling and recovery
    """

    # Backoff multiplier for retry delays
    BACKOFF_MULTIPLIER = 2
    INITIAL_BACKOFF_SECONDS = 1

    # Min/max backoff to prevent extreme delays
    MIN_BACKOFF = 1
    MAX_BACKOFF = 60

    def __init__(
        self,
        automation_run_id: int,
        tenant_id: int,
        agent_name: str,
        step_number: int,
        agent_function
    ):
        """
        Initialize agent loop.

        Args:
            automation_run_id: ID of parent AutomationRun
            tenant_id: Tenant ID for scoping
            agent_name: Name of agent (SamGovAgent, RFQAgent, etc)
            step_number: Step number in workflow (1-5)
            agent_function: Callable to execute
        """
        self.automation_run_id = automation_run_id
        self.tenant_id = tenant_id
        self.agent_name = agent_name
        self.step_number = step_number
        self.agent_function = agent_function

        # Get max retries from tenant subscription tier
        self.max_retries = self._get_max_retries()

        logger.info(
            f"AgentLoop initialized: {agent_name} (step {step_number}), "
            f"max_retries={self.max_retries}",
            extra={
                'tenant_id': tenant_id,
                'run_id': automation_run_id,
                'agent': agent_name
            }
        )

    def _get_max_retries(self) -> int:
        """
        Get max retry count based on tenant subscription tier.

        Returns:
            Integer retry count (2-5)
        """
        try:
            tenant = Tenant.query.filter_by(id=self.tenant_id).first()
            if not tenant:
                return 3  # default

            tier = tenant.subscription_tier
            retries_by_tier = {
                'basic': 2,
                'pro': 3,
                'enterprise': 5
            }
            return retries_by_tier.get(tier, 3)

        except Exception as e:
            logger.error(f"Error getting max retries: {e}")
            return 3

    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Execute agent with automatic retry and logging.

        Args:
            *args: Arguments to pass to agent function
            **kwargs: Keyword arguments to pass to agent function

        Returns:
            Dict with execution results:
            {
                'success': bool,
                'result': any,
                'attempt': int,
                'error': str or None,
                'duration_ms': int
            }
        """
        attempt = 0
        last_error = None
        last_result = None

        while attempt < self.max_retries:
            try:
                # Create log entry
                log_entry = AgentLoopLog(
                    tenant_id=self.tenant_id,
                    automation_run_id=self.automation_run_id,
                    agent_name=self.agent_name,
                    step_number=self.step_number,
                    status='running',
                    attempt_number=attempt + 1,
                    retry_count_max=self.max_retries,
                    start_time=datetime.utcnow()
                )
                db.session.add(log_entry)
                db.session.commit()

                logger.info(
                    f"Agent execution started (attempt {attempt + 1}/{self.max_retries})",
                    extra={
                        'tenant_id': self.tenant_id,
                        'run_id': self.automation_run_id,
                        'agent': self.agent_name,
                        'attempt': attempt + 1
                    }
                )

                # Execute agent
                start_time = time.time()
                result = self.agent_function(*args, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)

                # Success
                log_entry.status = 'success'
                log_entry.end_time = datetime.utcnow()
                log_entry.log_output = f"Execution completed successfully in {duration_ms}ms"
                db.session.commit()

                logger.info(
                    f"Agent execution succeeded (attempt {attempt + 1})",
                    extra={
                        'tenant_id': self.tenant_id,
                        'run_id': self.automation_run_id,
                        'agent': self.agent_name,
                        'duration_ms': duration_ms
                    }
                )

                return {
                    'success': True,
                    'result': result,
                    'attempt': attempt + 1,
                    'error': None,
                    'duration_ms': duration_ms
                }

            except Exception as e:
                last_error = str(e)
                attempt += 1

                # Determine if we should retry
                should_retry = attempt < self.max_retries

                log_entry.status = 'retry' if should_retry else 'failed'
                log_entry.error_message = last_error
                log_entry.attempt_number = attempt
                log_entry.end_time = datetime.utcnow()

                if should_retry:
                    # Calculate backoff delay
                    backoff_delay = self._calculate_backoff(attempt)
                    log_entry.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_delay)
                    log_entry.log_output = f"Execution failed. Retrying in {backoff_delay}s"

                    db.session.commit()

                    logger.warning(
                        f"Agent execution failed, retrying in {backoff_delay}s "
                        f"(attempt {attempt}/{self.max_retries}): {last_error}",
                        extra={
                            'tenant_id': self.tenant_id,
                            'run_id': self.automation_run_id,
                            'agent': self.agent_name,
                            'attempt': attempt
                        }
                    )

                    # Sleep before retry
                    time.sleep(backoff_delay)

                else:
                    # No more retries
                    log_entry.log_output = f"Final failure after {self.max_retries} attempts"
                    db.session.commit()

                    logger.error(
                        f"Agent execution failed after {self.max_retries} attempts: {last_error}",
                        extra={
                            'tenant_id': self.tenant_id,
                            'run_id': self.automation_run_id,
                            'agent': self.agent_name,
                            'attempts': self.max_retries
                        }
                    )

                    return {
                        'success': False,
                        'result': None,
                        'attempt': attempt,
                        'error': last_error,
                        'duration_ms': None
                    }

    def _calculate_backoff(self, attempt: int) -> int:
        """
        Calculate exponential backoff delay.

        Formula: min(max(2^attempt, 1), 60)

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Backoff delay in seconds
        """
        delay = self.INITIAL_BACKOFF_SECONDS * (self.BACKOFF_MULTIPLIER ** (attempt - 1))
        delay = max(delay, self.MIN_BACKOFF)
        delay = min(delay, self.MAX_BACKOFF)
        return int(delay)

    @staticmethod
    def get_agent_logs(
        automation_run_id: int,
        tenant_id: int,
        agent_name: Optional[str] = None,
        step_number: Optional[int] = None
    ) -> list:
        """
        Retrieve logs for agent execution.

        Args:
            automation_run_id: AutomationRun ID
            tenant_id: Tenant ID
            agent_name: Filter by agent name (optional)
            step_number: Filter by step number (optional)

        Returns:
            List of AgentLoopLog records
        """
        query = AgentLoopLog.query.filter_by(
            automation_run_id=automation_run_id,
            tenant_id=tenant_id
        )

        if agent_name:
            query = query.filter_by(agent_name=agent_name)

        if step_number:
            query = query.filter_by(step_number=step_number)

        return query.order_by(AgentLoopLog.created_at).all()

    @staticmethod
    def get_summary(automation_run_id: int, tenant_id: int) -> Dict[str, Any]:
        """
        Get summary of all agent execution for an automation run.

        Args:
            automation_run_id: AutomationRun ID
            tenant_id: Tenant ID

        Returns:
            Dict with summary stats
        """
        logs = AgentLoopLog.query.filter_by(
            automation_run_id=automation_run_id,
            tenant_id=tenant_id
        ).all()

        if not logs:
            return {
                'total_agents': 0,
                'successful': 0,
                'failed': 0,
                'total_attempts': 0,
                'agents': {}
            }

        summary = {
            'total_agents': len(set(log.agent_name for log in logs)),
            'successful': len([log for log in logs if log.status == 'success']),
            'failed': len([log for log in logs if log.status == 'failed']),
            'total_attempts': len(logs),
            'agents': {}
        }

        # Per-agent details
        for log in logs:
            if log.agent_name not in summary['agents']:
                summary['agents'][log.agent_name] = {
                    'step': log.step_number,
                    'status': log.status,
                    'attempts': 0,
                    'duration_ms': None
                }

            agent_summary = summary['agents'][log.agent_name]
            agent_summary['attempts'] += 1
            agent_summary['status'] = log.status

            if log.end_time and log.start_time:
                duration = (log.end_time - log.start_time).total_seconds() * 1000
                agent_summary['duration_ms'] = int(duration)

        return summary
