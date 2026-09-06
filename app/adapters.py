"""
Multi-Tenant Agent Adapter
Wraps existing agents to integrate with SaaS platform while maintaining backward compatibility
"""

import logging
from typing import Dict, Any, Optional
from app import db
from app.models import Solicitation, RFQOutput, Vendor

logger = logging.getLogger(__name__)


class SamGovAgentAdapter:
    """
    Adapter for SamGovAgent to work with multi-tenant SaaS platform.

    Wraps existing SamGovAgent and handles:
    - Tenant ID scoping
    - Database integration with new models
    - Error handling and retry logic
    """

    def __init__(self, tenant_id: int, automation_run_id: int):
        """
        Initialize adapter.

        Args:
            tenant_id: Tenant ID for scoping
            automation_run_id: Parent AutomationRun ID
        """
        self.tenant_id = tenant_id
        self.automation_run_id = automation_run_id

        # Import and initialize legacy agent
        from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent as LegacySamGovAgent
        self.legacy_agent = LegacySamGovAgent()

        logger.info(
            f"SamGovAgentAdapter initialized",
            extra={
                'tenant_id': tenant_id,
                'run_id': automation_run_id
            }
        )

    def execute(self) -> Dict[str, Any]:
        """
        Execute SAM.gov scraping for tenant.

        Returns:
            Dict with count of solicitations found
        """
        try:
            # Start browser
            self.legacy_agent.start_browser()

            # Perform search (using default keywords from config)
            from config import SAM_GOV_SEARCH_KEYWORDS
            keywords = SAM_GOV_SEARCH_KEYWORDS or ['procurement', 'supplies']

            all_solicitations = []

            for keyword in keywords[:3]:  # Limit to first 3 keywords
                logger.info(
                    f"Searching SAM.gov for: {keyword}",
                    extra={'tenant_id': self.tenant_id, 'run_id': self.automation_run_id}
                )

                try:
                    # Use legacy agent's search method
                    links = self.legacy_agent.search_for_links(keyword, start_page=0, num_pages=2)

                    if not links:
                        logger.warning(f"No solicitations found for keyword: {keyword}")
                        continue

                    # Process first 5 solicitations per keyword
                    for link in links[:5]:
                        try:
                            solicitation_data = self.legacy_agent.process_detail_page(link)

                            if solicitation_data:
                                # Save to database with tenant scoping
                                solicitation = Solicitation(
                                    tenant_id=self.tenant_id,
                                    contract_id=solicitation_data.get('contract_id', 'unknown'),
                                    url=link,
                                    title=solicitation_data.get('title'),
                                    description=solicitation_data.get('description'),
                                    location=solicitation_data.get('location', 'USA'),
                                    data=solicitation_data,
                                    review_status='pending'
                                )
                                db.session.add(solicitation)
                                all_solicitations.append(solicitation_data)

                                logger.info(
                                    f"Solicitation saved: {solicitation_data.get('contract_id')}",
                                    extra={'tenant_id': self.tenant_id}
                                )

                        except Exception as e:
                            logger.warning(
                                f"Failed to process solicitation {link}: {e}",
                                extra={'tenant_id': self.tenant_id}
                            )
                            continue

                except Exception as e:
                    logger.warning(
                        f"Search for keyword '{keyword}' failed: {e}",
                        extra={'tenant_id': self.tenant_id}
                    )
                    continue

            db.session.commit()

            logger.info(
                f"SAM.gov scraping completed: {len(all_solicitations)} solicitations",
                extra={
                    'tenant_id': self.tenant_id,
                    'run_id': self.automation_run_id,
                    'count': len(all_solicitations)
                }
            )

            return {
                'success': True,
                'count': len(all_solicitations),
                'solicitations': all_solicitations
            }

        except Exception as e:
            logger.error(
                f"SamGovAgentAdapter execute failed: {e}",
                extra={'tenant_id': self.tenant_id, 'run_id': self.automation_run_id},
                exc_info=True
            )
            raise

        finally:
            # Cleanup
            try:
                self.legacy_agent.close()
            except:
                pass

    def close(self):
        """Cleanup resources"""
        try:
            self.legacy_agent.close()
        except:
            pass


class RFQAgentAdapter:
    """
    Adapter for AttachmentReaderAgent to work with multi-tenant SaaS platform.
    """

    def __init__(self, tenant_id: int, automation_run_id: int):
        """Initialize adapter."""
        self.tenant_id = tenant_id
        self.automation_run_id = automation_run_id

        # Import and initialize legacy agent
        from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent as LegacyRFQAgent
        self.legacy_agent = LegacyRFQAgent()

        logger.info(
            f"RFQAgentAdapter initialized",
            extra={'tenant_id': tenant_id, 'run_id': automation_run_id}
        )

    def execute(self) -> Dict[str, Any]:
        """
        Generate RFQs for all tenant solicitations.

        Returns:
            Dict with count of RFQs generated
        """
        try:
            # Get tenant's solicitations
            solicitations = Solicitation.query.filter_by(
                tenant_id=self.tenant_id,
                review_status='pending'
            ).limit(10).all()

            if not solicitations:
                logger.warning(
                    "No solicitations to generate RFQs for",
                    extra={'tenant_id': self.tenant_id}
                )
                return {'success': True, 'count': 0, 'rfqs': []}

            generated_rfqs = []

            for solicitation in solicitations:
                try:
                    logger.info(
                        f"Generating RFQ for: {solicitation.contract_id}",
                        extra={'tenant_id': self.tenant_id}
                    )

                    # Use legacy agent to generate RFQ
                    gen_result = self.legacy_agent.create_summary_report(
                        solicitation.contract_id,
                        skip_json=True,
                        strict_fidelity=True,
                        enable_self_healing=True,
                        max_healing_iterations=2
                    )

                    if 'error' in gen_result:
                        logger.warning(
                            f"RFQ generation failed for {solicitation.contract_id}: {gen_result['error']}",
                            extra={'tenant_id': self.tenant_id}
                        )
                        continue

                    # Save RFQ to database with tenant scoping
                    rfq = RFQOutput(
                        tenant_id=self.tenant_id,
                        contract_id=solicitation.contract_id,
                        rfq_type=gen_result.get('rfq_type', 'UNKNOWN'),
                        rfq_content=gen_result.get('rfq_content', ''),
                        format='markdown'
                    )
                    db.session.add(rfq)
                    generated_rfqs.append(gen_result)

                    # Mark solicitation as processed
                    solicitation.review_status = 'processed'

                    logger.info(
                        f"RFQ generated and saved: {solicitation.contract_id}",
                        extra={'tenant_id': self.tenant_id}
                    )

                except Exception as e:
                    logger.warning(
                        f"Failed to generate RFQ for {solicitation.contract_id}: {e}",
                        extra={'tenant_id': self.tenant_id}
                    )
                    continue

            db.session.commit()

            logger.info(
                f"RFQ generation completed: {len(generated_rfqs)} RFQs",
                extra={
                    'tenant_id': self.tenant_id,
                    'run_id': self.automation_run_id,
                    'count': len(generated_rfqs)
                }
            )

            return {
                'success': True,
                'count': len(generated_rfqs),
                'rfqs': generated_rfqs
            }

        except Exception as e:
            logger.error(
                f"RFQAgentAdapter execute failed: {e}",
                extra={'tenant_id': self.tenant_id, 'run_id': self.automation_run_id},
                exc_info=True
            )
            raise


class VendorSearchAgentAdapter:
    """
    Adapter for ThomasNetSearch + EmailExtractor to work with multi-tenant SaaS.
    """

    def __init__(self, tenant_id: int, automation_run_id: int):
        """Initialize adapter."""
        self.tenant_id = tenant_id
        self.automation_run_id = automation_run_id

        logger.info(
            f"VendorSearchAgentAdapter initialized",
            extra={'tenant_id': tenant_id, 'run_id': automation_run_id}
        )

    def execute(self) -> Dict[str, Any]:
        """
        Search for vendors for all tenant RFQs.

        Returns:
            Dict with count of vendors found
        """
        try:
            from ai_agents.ThomasNetAgent.auth import ThomasNetAuth
            from ai_agents.ThomasNetAgent.searcher import ThomasNetSearch
            from ai_agents.ThomasNetAgent.email_extractor import EmailExtractor
            from ai_agents.ThomasNetAgent.rfq_parser import RFQParser

            # Get tenant's RFQs
            rfqs = RFQOutput.query.filter_by(tenant_id=self.tenant_id).limit(5).all()

            if not rfqs:
                logger.warning("No RFQs to search vendors for", extra={'tenant_id': self.tenant_id})
                return {'success': True, 'count': 0, 'vendors': []}

            all_vendors = []

            try:
                # Initialize ThomasNet session
                thomasnet_auth = ThomasNetAuth(headless=True)
                search_engine = ThomasNetSearch(thomasnet_auth)
                email_extractor = EmailExtractor(thomasnet_auth.page)
                parser = RFQParser()

                for rfq in rfqs:
                    try:
                        logger.info(
                            f"Searching vendors for RFQ: {rfq.contract_id}",
                            extra={'tenant_id': self.tenant_id}
                        )

                        # Parse RFQ to extract products
                        parsed = parser.parse_file(rfq.rfq_content)
                        products = parsed.get('products', [])

                        if not products:
                            logger.warning(f"No products found in RFQ {rfq.contract_id}")
                            continue

                        # Search for vendors per product
                        rfq_vendors = []

                        for product in products[:3]:  # Limit to first 3 products
                            product_name = product.get('name', '').strip()
                            if not product_name:
                                continue

                            try:
                                vendors = search_engine.search_vendors(product_name, max_results=5)

                                if vendors:
                                    logger.info(
                                        f"Found {len(vendors)} vendors for '{product_name}'",
                                        extra={'tenant_id': self.tenant_id}
                                    )

                                    # Extract emails
                                    vendors_with_emails = email_extractor.batch_extract_emails(vendors)
                                    rfq_vendors.extend(vendors_with_emails)

                            except Exception as e:
                                logger.warning(f"Vendor search for '{product_name}' failed: {e}")
                                continue

                        # Save vendors to database with tenant scoping
                        for vendor in rfq_vendors:
                            v = Vendor(
                                tenant_id=self.tenant_id,
                                contract_id=rfq.contract_id,
                                name=vendor.get('name', 'Unknown'),
                                website=vendor.get('website'),
                                email=vendor.get('email'),
                                phone=vendor.get('phone'),
                                location=vendor.get('location'),
                                confidence_score=vendor.get('confidence_score', 70),
                                email_status='Ready' if vendor.get('email') else 'No Contact'
                            )
                            db.session.add(v)
                            all_vendors.append(vendor)

                        logger.info(
                            f"Vendors saved for RFQ: {rfq.contract_id}",
                            extra={'tenant_id': self.tenant_id, 'count': len(rfq_vendors)}
                        )

                    except Exception as e:
                        logger.warning(
                            f"Vendor search for RFQ {rfq.contract_id} failed: {e}",
                            extra={'tenant_id': self.tenant_id}
                        )
                        continue

                db.session.commit()

            finally:
                try:
                    thomasnet_auth.close()
                except:
                    pass

            logger.info(
                f"Vendor search completed: {len(all_vendors)} vendors",
                extra={
                    'tenant_id': self.tenant_id,
                    'run_id': self.automation_run_id,
                    'count': len(all_vendors)
                }
            )

            return {
                'success': True,
                'count': len(all_vendors),
                'vendors': all_vendors
            }

        except Exception as e:
            logger.error(
                f"VendorSearchAgentAdapter execute failed: {e}",
                extra={'tenant_id': self.tenant_id, 'run_id': self.automation_run_id},
                exc_info=True
            )
            raise


class SubmissionAgentAdapter:
    """
    Adapter for RFQ submission (ThomasNet or Email) to work with multi-tenant SaaS.
    """

    def __init__(self, tenant_id: int, automation_run_id: int):
        """Initialize adapter."""
        self.tenant_id = tenant_id
        self.automation_run_id = automation_run_id

        logger.info(
            f"SubmissionAgentAdapter initialized",
            extra={'tenant_id': tenant_id, 'run_id': automation_run_id}
        )

    def execute(self, submission_method: str = 'email') -> Dict[str, Any]:
        """
        Submit RFQs to vendors.

        Args:
            submission_method: 'email' or 'thomasnet' or 'both'

        Returns:
            Dict with count of submissions sent
        """
        try:
            # Get tenant's vendors with emails
            vendors = Vendor.query.filter_by(
                tenant_id=self.tenant_id,
                email_status='Ready'
            ).filter(Vendor.email != None).limit(50).all()

            if not vendors:
                logger.warning("No vendors with emails to submit to", extra={'tenant_id': self.tenant_id})
                return {'success': True, 'count': 0, 'submissions': []}

            submissions = 0

            if submission_method in ['email', 'both']:
                # Email submission
                try:
                    submissions += self._submit_via_email(vendors)
                except Exception as e:
                    logger.warning(f"Email submission failed: {e}", extra={'tenant_id': self.tenant_id})

            if submission_method in ['thomasnet', 'both']:
                # ThomasNet submission (optional)
                try:
                    submissions += self._submit_via_thomasnet(vendors)
                except Exception as e:
                    logger.warning(f"ThomasNet submission failed: {e}", extra={'tenant_id': self.tenant_id})

            logger.info(
                f"RFQ submission completed: {submissions} submissions",
                extra={
                    'tenant_id': self.tenant_id,
                    'run_id': self.automation_run_id,
                    'count': submissions
                }
            )

            return {
                'success': True,
                'count': submissions,
                'submissions': submissions
            }

        except Exception as e:
            logger.error(
                f"SubmissionAgentAdapter execute failed: {e}",
                extra={'tenant_id': self.tenant_id, 'run_id': self.automation_run_id},
                exc_info=True
            )
            raise

    def _submit_via_email(self, vendors: list) -> int:
        """Submit RFQs via email"""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from config import SMTP_CONFIG

        if not SMTP_CONFIG.get('smtp_server'):
            logger.warning("SMTP not configured, skipping email submission")
            return 0

        submitted = 0

        for vendor in vendors[:10]:  # Limit to 10 per run
            try:
                # Get associated RFQ
                rfq = RFQOutput.query.filter_by(
                    tenant_id=self.tenant_id,
                    contract_id=vendor.contract_id
                ).first()

                if not rfq:
                    continue

                # Send email
                msg = MIMEMultipart()
                msg['From'] = SMTP_CONFIG.get('sender_email')
                msg['To'] = vendor.email
                msg['Subject'] = f"Request for Quote - {vendor.contract_id}"

                body = f"""Dear {vendor.name},

We are requesting a quote for products/services outlined in the attached RFQ.

Please review and submit your quote by the deadline specified.

Best regards,
Camp Sable LLC Procurement"""

                msg.attach(MIMEText(body, 'plain'))

                # Send
                with smtplib.SMTP(SMTP_CONFIG.get('smtp_server'), SMTP_CONFIG.get('smtp_port', 587)) as server:
                    server.starttls()
                    server.login(SMTP_CONFIG.get('smtp_username'), SMTP_CONFIG.get('smtp_password'))
                    server.send_message(msg)

                # Update status
                rfq.sent_to_vendor = True
                rfq.vendor_email_recipient = vendor.email
                rfq.sent_date = __import__('datetime').datetime.utcnow()

                vendor.email_status = 'Sent'
                db.session.commit()

                logger.info(
                    f"Email sent to {vendor.name} ({vendor.email})",
                    extra={'tenant_id': self.tenant_id}
                )
                submitted += 1

            except Exception as e:
                logger.warning(
                    f"Failed to email {vendor.name}: {e}",
                    extra={'tenant_id': self.tenant_id}
                )
                continue

        return submitted

    def _submit_via_thomasnet(self, vendors: list) -> int:
        """Submit RFQs via ThomasNet (placeholder)"""
        logger.info("ThomasNet submission not yet implemented", extra={'tenant_id': self.tenant_id})
        return 0
