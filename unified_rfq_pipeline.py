#!/usr/bin/env python3
"""
Unified RFQ Automation Pipeline
Orchestrates: SAM.gov scrape → RFQ generation → ThomasNet vendor search →
RFQ submission via ThomasNet OR direct email to verified vendor contacts
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional

# Add paths
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import config
from database_manager import DatabaseManager
from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ThomasNetAgent.rfq_parser import RFQParser
from ai_agents.ThomasNetAgent.searcher import ThomasNetSearch
from ai_agents.ThomasNetAgent.email_extractor import EmailExtractor
from ai_agents.ThomasNetAgent.auth import ThomasNetAuth
from utils.doc_converter import convert_md_to_docx

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedRFQPipeline:
    """Main orchestrator for the complete RFQ automation workflow."""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.sam_agent = None
        self.thomasnet_auth = None

    def run_complete_pipeline(self, solicitation_url: str, args: argparse.Namespace) -> Dict:
        """
        Execute the complete pipeline: scrape → generate → search → submit.

        Args:
            solicitation_url: SAM.gov solicitation URL
            args: Command-line arguments

        Returns:
            Dictionary with pipeline execution results
        """
        result = {
            "status": "pending",
            "contract_id": None,
            "rfq_generated": False,
            "vendors_found": 0,
            "submissions_successful": 0,
            "emails_sent": 0,
            "errors": []
        }

        try:
            # STEP 1: Scrape SAM.gov
            logger.info("=" * 80)
            logger.info("STEP 1: Scraping SAM.gov solicitation...")
            logger.info("=" * 80)

            self.sam_agent = SamGovAgent()
            self.sam_agent.start_browser()

            solicitation_data = self.sam_agent.process_detail_page(solicitation_url)
            if not solicitation_data:
                result["errors"].append("Failed to scrape solicitation data")
                result["status"] = "failed"
                return result

            contract_id = solicitation_data.get("contract_id")
            result["contract_id"] = contract_id
            logger.info(f"✓ Scraped solicitation: {contract_id}")

            # Save to DB
            self.db_manager.add_solicitation(
                contract_id=contract_id,
                url=solicitation_url,
                title=solicitation_data.get("title"),
                description=solicitation_data.get("description"),
                location="USA",
                product_requirements=None,
                analysis_summary=None,
                data=json.dumps(solicitation_data)
            )

            # STEP 2: Generate RFQ
            logger.info("=" * 80)
            logger.info("STEP 2: Generating RFQ document...")
            logger.info("=" * 80)

            reader = AttachmentReaderAgent()
            gen_result = reader.create_summary_report(
                contract_id,
                skip_json=True,
                strict_fidelity=args.strict_fidelity,
                enable_self_healing=not args.no_self_healing,
                max_healing_iterations=args.max_healing_iterations
            )

            if "error" in gen_result:
                result["errors"].append(f"RFQ generation failed: {gen_result['error']}")
                result["status"] = "failed"
                return result

            rfq_content = gen_result.get("rfq_content")
            rfq_type = gen_result.get("rfq_type", "UNKNOWN")
            result["rfq_generated"] = True

            # Save RFQ to DB
            self.db_manager.add_rfq_output(contract_id, rfq_type, rfq_content, format="docx")

            # Convert to DOCX
            filename = f"{contract_id}_RFQ_{rfq_type}.docx"
            output_dir = os.path.join("rfq_downloads", datetime.now().strftime("%Y-%m-%d"))
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, filename)

            logger.info(f"Converting RFQ to DOCX...")
            saved_docx = convert_md_to_docx(rfq_content, output_path)

            if not saved_docx:
                # Fallback to markdown
                md_path = output_path.replace(".docx", ".md")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(rfq_content)
                output_path = md_path
                logger.warning(f"DOCX conversion failed. Using markdown: {md_path}")
            else:
                logger.info(f"✓ RFQ saved: {output_path}")

            # STEP 3: Parse RFQ to extract products
            logger.info("=" * 80)
            logger.info("STEP 3: Extracting products from RFQ...")
            logger.info("=" * 80)

            parser = RFQParser()
            parsed_rfq = parser.parse_file(output_path)

            if not parsed_rfq.get("products"):
                result["errors"].append("No products extracted from RFQ")
                logger.warning("No products found in RFQ")
            else:
                logger.info(f"✓ Extracted {len(parsed_rfq['products'])} product(s)")
                for product in parsed_rfq["products"]:
                    logger.info(f"  - {product['name']} (Qty: {product['quantity']})")

            # STEP 4: Search for vendors on ThomasNet
            logger.info("=" * 80)
            logger.info("STEP 4: Searching for vendors on ThomasNet...")
            logger.info("=" * 80)

            if not args.skip_thomasnet_search:
                try:
                    self.thomasnet_auth = ThomasNetAuth(headless=args.thomasnet_headless)
                    search_engine = ThomasNetSearch(self.thomasnet_auth)
                    email_extractor = EmailExtractor(self.thomasnet_auth.page)

                    # Search for each product
                    all_vendors = []
                    for product in parsed_rfq.get("products", [])[:3]:  # Limit to first 3 products
                        product_name = product.get("name", "").strip()
                        if not product_name:
                            continue

                        logger.info(f"Searching for: {product_name}")
                        vendors = search_engine.search_vendors(
                            product_name,
                            max_results=args.thomasnet_max_vendors
                        )

                        if vendors:
                            logger.info(f"✓ Found {len(vendors)} vendors for '{product_name}'")
                            all_vendors.extend(vendors)

                    result["vendors_found"] = len(all_vendors)

                    if all_vendors:
                        # STEP 5: Extract vendor emails
                        logger.info("=" * 80)
                        logger.info("STEP 5: Extracting vendor contact emails...")
                        logger.info("=" * 80)

                        all_vendors = email_extractor.batch_extract_emails(all_vendors)

                        # Save vendors to DB
                        for vendor in all_vendors:
                            self.db_manager.add_vendor(
                                contract_id=contract_id,
                                name=vendor.get("name", "Unknown"),
                                website=vendor.get("website"),
                                email=vendor.get("email"),
                                phone=None,
                                confidence_score=80,
                                has_gov_page=False,
                                has_past_performance=False,
                                gov_agencies_worked_with=None,
                                past_performance_summary=None,
                                key_personnel=None,
                                linkedin_url=None,
                                place_types=vendor.get("location"),
                                email_status="Ready" if vendor.get("email") else "No Contact"
                            )

                        # STEP 6: Submit RFQ
                        logger.info("=" * 80)
                        logger.info("STEP 6: Submitting RFQ to vendors...")
                        logger.info("=" * 80)

                        if args.submission_method == "thomasnet":
                            # ThomasNet batch submission
                            result["submissions_successful"] = self._submit_via_thomasnet(
                                all_vendors, output_path, contract_id
                            )
                        elif args.submission_method == "email":
                            # Direct email submission
                            result["emails_sent"] = self._submit_via_email(
                                all_vendors, rfq_content, output_path, contract_id
                            )
                        elif args.submission_method == "both":
                            # Try ThomasNet first, then email as fallback
                            result["submissions_successful"] = self._submit_via_thomasnet(
                                all_vendors, output_path, contract_id
                            )
                            result["emails_sent"] = self._submit_via_email(
                                all_vendors, rfq_content, output_path, contract_id
                            )

                except Exception as e:
                    result["errors"].append(f"ThomasNet workflow failed: {str(e)}")
                    logger.error(f"ThomasNet workflow error: {e}", exc_info=True)

            result["status"] = "completed"

        except Exception as e:
            result["status"] = "failed"
            result["errors"].append(str(e))
            logger.error(f"Pipeline error: {e}", exc_info=True)

        finally:
            # Cleanup
            if self.sam_agent:
                self.sam_agent.close()
            if self.thomasnet_auth:
                try:
                    self.thomasnet_auth.close()
                except:
                    pass

        return result

    def _submit_via_thomasnet(self, vendors: List[Dict], rfq_path: str, contract_id: str) -> int:
        """Submit RFQ via ThomasNet batch system."""
        try:
            from ai_agents.ThomasNetAgent.form_filler import RFQFormFiller

            filler = RFQFormFiller(self.thomasnet_auth)

            # Select vendors with valid emails
            selected_vendors = [v for v in vendors if v.get("email")][:5]

            if not selected_vendors:
                logger.warning("No vendors with emails available for ThomasNet submission")
                return 0

            # Submit RFQ
            result = filler.submit_multi_vendor_rfq(
                vendors=selected_vendors,
                rfq_file_path=rfq_path,
                contract_id=contract_id
            )

            if result.get("success"):
                logger.info(f"✓ Submitted RFQ to {result.get('vendors_contacted', 0)} vendors via ThomasNet")
                return result.get("vendors_contacted", 0)
            else:
                logger.warning(f"ThomasNet submission failed: {result.get('error')}")
                return 0

        except Exception as e:
            logger.error(f"ThomasNet submission error: {e}")
            return 0

    def _submit_via_email(self, vendors: List[Dict], rfq_content: str, rfq_path: str, contract_id: str) -> int:
        """Submit RFQ via direct email to vendors."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders

            # Get SMTP config
            smtp_config = config.SMTP_CONFIG
            if not all([smtp_config.get("smtp_server"), smtp_config.get("smtp_username"),
                       smtp_config.get("smtp_password"), smtp_config.get("sender_email")]):
                logger.warning("SMTP config incomplete, skipping email submission")
                return 0

            emails_sent = 0

            # Select vendors with valid emails
            selected_vendors = [v for v in vendors if v.get("email")][:10]

            for vendor in selected_vendors:
                try:
                    vendor_email = vendor.get("email")
                    vendor_name = vendor.get("name", "Valued Partner")

                    # Create email
                    msg = MIMEMultipart()
                    msg["From"] = smtp_config.get("sender_email")
                    msg["To"] = vendor_email
                    msg["Subject"] = f"Request for Quote - {contract_id}"

                    # Email body
                    body = f"""
Dear {vendor_name},

We are writing to request a formal quote for products/services listed in the attached RFQ document.

Camp Sable, LLC is a registered government procurement contractor seeking qualified suppliers for the
requirements outlined in this RFQ.

Please review the attached document and provide your quote by the deadline specified.

If you have any questions or need clarification, please don't hesitate to contact us.

Thank you for your consideration.

Best regards,
{config.COMPANY_INFO.get('COMPANY_SNAPSHOT', {}).get('Point of Contact', 'Camp Sable Procurement')}
{config.COMPANY_INFO.get('COMPANY_SNAPSHOT', {}).get('Email', config.RFQ_VENDOR_EMAIL)}
{config.COMPANY_INFO.get('COMPANY_SNAPSHOT', {}).get('Phone Number', '')}
"""

                    msg.attach(MIMEText(body, "plain"))

                    # Attach RFQ document
                    if os.path.exists(rfq_path):
                        with open(rfq_path, "rb") as attachment:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(rfq_path)}")
                        msg.attach(part)

                    # Send email
                    with smtplib.SMTP(smtp_config.get("smtp_server"), int(smtp_config.get("smtp_port", 587))) as server:
                        server.starttls()
                        server.login(smtp_config.get("smtp_username"), smtp_config.get("smtp_password"))
                        server.send_message(msg)

                    logger.info(f"✓ Email sent to {vendor_name} ({vendor_email})")
                    emails_sent += 1

                    # Mark as sent in DB
                    self.db_manager.mark_rfq_sent(contract_id, vendor_email)

                except Exception as e:
                    logger.error(f"Failed to send email to {vendor.get('name', 'Unknown')}: {e}")
                    continue

            logger.info(f"Email submission complete: {emails_sent} emails sent")
            return emails_sent

        except Exception as e:
            logger.error(f"Email submission workflow error: {e}")
            return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Unified RFQ Automation Pipeline")

    parser.add_argument("--url", type=str, required=True, help="SAM.gov solicitation URL")
    parser.add_argument("--strict-fidelity", action="store_true", help="Enforce strict template fidelity")
    parser.add_argument("--no-self-healing", action="store_true", help="Disable RFQ self-healing")
    parser.add_argument("--max-healing-iterations", type=int, default=3, help="Max self-healing iterations")
    parser.add_argument("--skip-thomasnet-search", action="store_true", help="Skip ThomasNet vendor search")
    parser.add_argument("--thomasnet-max-vendors", type=int, default=5, help="Max vendors per product")
    parser.add_argument("--thomasnet-headless", action="store_true", default=True, help="Run ThomasNet headless")
    parser.add_argument(
        "--submission-method",
        type=str,
        choices=["thomasnet", "email", "both"],
        default="both",
        help="How to submit RFQ: ThomasNet, email, or both"
    )

    args = parser.parse_args()

    logger.info("Starting Unified RFQ Pipeline...")
    logger.info(f"Target URL: {args.url}")

    pipeline = UnifiedRFQPipeline()
    result = pipeline.run_complete_pipeline(args.url, args)

    logger.info("=" * 80)
    logger.info("PIPELINE EXECUTION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Status: {result['status']}")
    logger.info(f"Contract ID: {result['contract_id']}")
    logger.info(f"RFQ Generated: {result['rfq_generated']}")
    logger.info(f"Vendors Found: {result['vendors_found']}")
    logger.info(f"ThomasNet Submissions: {result['submissions_successful']}")
    logger.info(f"Emails Sent: {result['emails_sent']}")

    if result["errors"]:
        logger.warning("Errors encountered:")
        for error in result["errors"]:
            logger.warning(f"  - {error}")

    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
