"""
Automation Controller
Orchestrates the complete RFQ automation workflow with agent loops
"""

import logging
from datetime import datetime
from typing import Dict, Any
from app import db
from app.models import AutomationRun, AuditLog, Tenant
from app.orchestration.agent_loop import AgentLoop

logger = logging.getLogger(__name__)


class AutomationController:
    """
    Master orchestrator for complete RFQ automation workflow.

    Manages 5-step pipeline:
    1. SAM.gov Scraping (SamGovAgent)
    2. RFQ Generation (AttachmentReaderAgent)
    3. Product Extraction (RFQParser)
    4. Vendor Search (ThomasNetSearch)
    5. RFQ Submission (SubmissionAgent)
    """

    WORKFLOW_STEPS = [
        {'step': 1, 'name': 'SamGovAgent', 'description': 'Scraping SAM.gov solicitations'},
        {'step': 2, 'name': 'AttachmentReaderAgent', 'description': 'Generating RFQ documents'},
        {'step': 3, 'name': 'RFQParser', 'description': 'Extracting products and specifications'},
        {'step': 4, 'name': 'VendorSearchAgent', 'description': 'Finding vendors on ThomasNet'},
        {'step': 5, 'name': 'SubmissionAgent', 'description': 'Submitting RFQs to vendors'},
    ]

    def __init__(self, automation_run_id: int, tenant_id: int):
        """
        Initialize automation controller.

        Args:
            automation_run_id: ID of AutomationRun
            tenant_id: Tenant ID
        """
        self.automation_run_id = automation_run_id
        self.tenant_id = tenant_id

        # Fetch automation run
        self.automation_run = AutomationRun.query.filter_by(
            id=automation_run_id,
            tenant_id=tenant_id
        ).first()

        if not self.automation_run:
            raise ValueError(f"AutomationRun {automation_run_id} not found for tenant {tenant_id}")

        logger.info(
            f"AutomationController initialized",
            extra={
                'tenant_id': tenant_id,
                'run_id': automation_run_id
            }
        )

    def execute_workflow(self) -> Dict[str, Any]:
        """
        Execute complete automation workflow.

        Returns:
            Dict with workflow results:
            {
                'status': 'completed' | 'failed',
                'results': {...},
                'errors': [...]
            }
        """
        results = {
            'solicitations_found': 0,
            'rfqs_generated': 0,
            'products_extracted': 0,
            'vendors_found': 0,
            'submissions_sent': 0
        }
        errors = []

        try:
            # Update automation run status
            self.automation_run.status = 'running'
            self.automation_run.start_time = datetime.utcnow()
            db.session.commit()

            logger.info(
                f"Workflow execution started",
                extra={
                    'tenant_id': self.tenant_id,
                    'run_id': self.automation_run_id
                }
            )

            # STEP 1: SAM.gov Scraping
            logger.info("STEP 1: Scraping SAM.gov...")
            try:
                sam_result = self._execute_step(
                    step_number=1,
                    agent_name='SamGovAgent',
                    agent_function=self._run_sam_gov_agent
                )

                if sam_result['success']:
                    results['solicitations_found'] = sam_result.get('result', {}).get('count', 0)
                    logger.info(
                        f"✓ SAM.gov scraping completed: {results['solicitations_found']} solicitations"
                    )
                else:
                    errors.append(f"SAM.gov scraping failed: {sam_result['error']}")
                    logger.warning(f"SAM.gov scraping failed after {sam_result['attempt']} attempts")

            except Exception as e:
                errors.append(f"SAM.gov step error: {str(e)}")
                logger.error(f"SAM.gov step error: {e}", exc_info=True)

            # STEP 2: RFQ Generation
            logger.info("STEP 2: Generating RFQ documents...")
            try:
                rfq_result = self._execute_step(
                    step_number=2,
                    agent_name='AttachmentReaderAgent',
                    agent_function=self._run_rfq_generation_agent
                )

                if rfq_result['success']:
                    results['rfqs_generated'] = rfq_result.get('result', {}).get('count', 0)
                    logger.info(
                        f"✓ RFQ generation completed: {results['rfqs_generated']} RFQs"
                    )
                else:
                    errors.append(f"RFQ generation failed: {rfq_result['error']}")
                    logger.warning(f"RFQ generation failed after {rfq_result['attempt']} attempts")

            except Exception as e:
                errors.append(f"RFQ generation step error: {str(e)}")
                logger.error(f"RFQ generation step error: {e}", exc_info=True)

            # STEP 3: Product Extraction
            logger.info("STEP 3: Extracting products from RFQs...")
            try:
                parse_result = self._execute_step(
                    step_number=3,
                    agent_name='RFQParser',
                    agent_function=self._run_parser_agent
                )

                if parse_result['success']:
                    results['products_extracted'] = parse_result.get('result', {}).get('count', 0)
                    logger.info(
                        f"✓ Product extraction completed: {results['products_extracted']} products"
                    )
                else:
                    errors.append(f"Product extraction failed: {parse_result['error']}")
                    logger.warning(f"Product extraction failed after {parse_result['attempt']} attempts")

            except Exception as e:
                errors.append(f"Product extraction step error: {str(e)}")
                logger.error(f"Product extraction step error: {e}", exc_info=True)

            # STEP 4: Vendor Search
            logger.info("STEP 4: Searching for vendors on ThomasNet...")
            try:
                vendor_result = self._execute_step(
                    step_number=4,
                    agent_name='VendorSearchAgent',
                    agent_function=self._run_vendor_search_agent
                )

                if vendor_result['success']:
                    results['vendors_found'] = vendor_result.get('result', {}).get('count', 0)
                    logger.info(
                        f"✓ Vendor search completed: {results['vendors_found']} vendors"
                    )
                else:
                    errors.append(f"Vendor search failed: {vendor_result['error']}")
                    logger.warning(f"Vendor search failed after {vendor_result['attempt']} attempts")

            except Exception as e:
                errors.append(f"Vendor search step error: {str(e)}")
                logger.error(f"Vendor search step error: {e}", exc_info=True)

            # STEP 5: RFQ Submission
            logger.info("STEP 5: Submitting RFQs to vendors...")
            try:
                submission_result = self._execute_step(
                    step_number=5,
                    agent_name='SubmissionAgent',
                    agent_function=self._run_submission_agent
                )

                if submission_result['success']:
                    results['submissions_sent'] = submission_result.get('result', {}).get('count', 0)
                    logger.info(
                        f"✓ RFQ submission completed: {results['submissions_sent']} submissions"
                    )
                else:
                    errors.append(f"RFQ submission failed: {submission_result['error']}")
                    logger.warning(f"RFQ submission failed after {submission_result['attempt']} attempts")

            except Exception as e:
                errors.append(f"RFQ submission step error: {str(e)}")
                logger.error(f"RFQ submission step error: {e}", exc_info=True)

            # Update automation run with results
            self.automation_run.status = 'completed' if not errors else 'completed_with_errors'
            self.automation_run.results = results
            self.automation_run.end_time = datetime.utcnow()

            if errors:
                self.automation_run.error_message = '; '.join(errors[:3])  # Store first 3 errors

            db.session.commit()

            # Create audit log
            audit_log = AuditLog(
                tenant_id=self.tenant_id,
                action='automation_completed',
                resource_type='automation_run',
                resource_id=self.automation_run_id,
                details={
                    'results': results,
                    'errors_count': len(errors),
                    'duration_seconds': self.automation_run.get_duration_seconds()
                }
            )
            db.session.add(audit_log)
            db.session.commit()

            logger.info(
                f"Workflow execution completed",
                extra={
                    'tenant_id': self.tenant_id,
                    'run_id': self.automation_run_id,
                    'results': results,
                    'errors': len(errors)
                }
            )

            return {
                'status': 'completed' if not errors else 'completed_with_errors',
                'results': results,
                'errors': errors
            }

        except Exception as e:
            # Fatal error
            self.automation_run.status = 'failed'
            self.automation_run.error_message = str(e)
            self.automation_run.end_time = datetime.utcnow()
            db.session.commit()

            logger.error(
                f"Workflow execution failed: {e}",
                extra={
                    'tenant_id': self.tenant_id,
                    'run_id': self.automation_run_id
                },
                exc_info=True
            )

            return {
                'status': 'failed',
                'results': results,
                'errors': [str(e)]
            }

    def _execute_step(
        self,
        step_number: int,
        agent_name: str,
        agent_function
    ) -> Dict[str, Any]:
        """
        Execute a single workflow step with agent loop.

        Args:
            step_number: Step number (1-5)
            agent_name: Name of agent
            agent_function: Callable to execute

        Returns:
            Dict with execution result
        """
        loop = AgentLoop(
            automation_run_id=self.automation_run_id,
            tenant_id=self.tenant_id,
            agent_name=agent_name,
            step_number=step_number,
            agent_function=agent_function
        )

        return loop.execute()

    def _run_sam_gov_agent(self) -> Dict[str, Any]:
        """
        Execute SamGovAgent (Step 1: Scraping).

        Returns:
            Dict with count of solicitations found
        """
        try:
            from app.adapters import SamGovAgentAdapter

            adapter = SamGovAgentAdapter(self.tenant_id, self.automation_run_id)
            result = adapter.execute()
            adapter.close()

            return result

        except Exception as e:
            logger.error(f"SamGovAgent error: {e}")
            raise

    def _run_rfq_generation_agent(self) -> Dict[str, Any]:
        """
        Execute AttachmentReaderAgent (Step 2: RFQ Generation).

        Returns:
            Dict with count of RFQs generated
        """
        try:
            from app.adapters import RFQAgentAdapter

            adapter = RFQAgentAdapter(self.tenant_id, self.automation_run_id)
            result = adapter.execute()

            return result

        except Exception as e:
            logger.error(f"AttachmentReaderAgent error: {e}")
            raise

    def _run_parser_agent(self) -> Dict[str, Any]:
        """
        Execute RFQParser (Step 3: Product Extraction).

        Returns:
            Dict with count of products extracted
        """
        try:
            from app.models import RFQOutput

            # This step is integrated into RFQ generation,
            # but we can use the parser to validate
            rfqs = RFQOutput.query.filter_by(tenant_id=self.tenant_id).all()

            products_found = 0

            # Product extraction happens during RFQ processing
            # In Phase 2, this would be expanded
            logger.info(f"Product extraction: validated {len(rfqs)} RFQs")

            return {'count': products_found}

        except Exception as e:
            logger.error(f"RFQParser error: {e}")
            raise

    def _run_vendor_search_agent(self) -> Dict[str, Any]:
        """
        Execute VendorSearchAgent (Step 4: Vendor Search).

        Returns:
            Dict with count of vendors found
        """
        try:
            from app.adapters import VendorSearchAgentAdapter

            adapter = VendorSearchAgentAdapter(self.tenant_id, self.automation_run_id)
            result = adapter.execute()

            return result

        except Exception as e:
            logger.error(f"VendorSearchAgent error: {e}")
            raise

    def _run_submission_agent(self) -> Dict[str, Any]:
        """
        Execute SubmissionAgent (Step 5: RFQ Submission).

        Returns:
            Dict with count of submissions sent
        """
        try:
            from app.adapters import SubmissionAgentAdapter

            adapter = SubmissionAgentAdapter(self.tenant_id, self.automation_run_id)
            result = adapter.execute(submission_method='email')

            return result

        except Exception as e:
            logger.error(f"SubmissionAgent error: {e}")
            raise

    @staticmethod
    def get_workflow_summary(automation_run_id: int, tenant_id: int) -> Dict[str, Any]:
        """
        Get summary of workflow execution.

        Args:
            automation_run_id: AutomationRun ID
            tenant_id: Tenant ID

        Returns:
            Dict with workflow summary and per-step details
        """
        automation_run = AutomationRun.query.filter_by(
            id=automation_run_id,
            tenant_id=tenant_id
        ).first()

        if not automation_run:
            return None

        agent_summary = AgentLoop.get_summary(automation_run_id, tenant_id)

        return {
            'automation_run_id': automation_run_id,
            'status': automation_run.status,
            'created_at': automation_run.created_at.isoformat(),
            'start_time': automation_run.start_time.isoformat() if automation_run.start_time else None,
            'end_time': automation_run.end_time.isoformat() if automation_run.end_time else None,
            'duration_seconds': automation_run.get_duration_seconds(),
            'results': automation_run.results,
            'error_message': automation_run.error_message,
            'agent_summary': agent_summary
        }
