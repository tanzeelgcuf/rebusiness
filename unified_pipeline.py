#!/usr/bin/env python3
"""
Unified RFQ Automation Pipeline

Complete end-to-end pipeline:
1. Scrape SAM.gov solicitations with all attachments
2. Process attachments and generate high-fidelity RFQ documents
3. Search ThomasNet for vendors by product keywords
4. Submit RFQs via ThomasNet batch system AND/OR direct email outreach

Usage:
    python unified_pipeline.py --keyword "industrial fasteners" --max-solicitations 5
    python unified_pipeline.py --url "https://sam.gov/opp/..." --submit-thomasnet --email-outreach
    python unified_pipeline.py --scheduled --hours 3
"""

import os
import sys
import json
import time
import logging
import argparse
import schedule
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add project paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import config
from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent
from ai_agents.ThomasNetAgent.searcher import ThomasNetSearch
from ai_agents.ThomasNetAgent.rfq_parser import RFQParser
from ai_agents.ThomasNetAgent.vendor_email_extractor import extract_vendor_emails, VendorContact
from ai_agents.OutreachAgent.email_sender import EmailSender, EmailResult
from ai_agents.ThomasNetAgent.auth import ThomasNetAuth
from database_manager import DatabaseManager
from utils.doc_converter import convert_md_to_docx

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedPipeline:
    """
    Orchestrates the complete RFQ automation workflow.
    """

    def __init__(
        self,
        llm_provider: str = "gemini",
        max_vendors_per_product: int = 5,
        submit_to_thomasnet: bool = True,
        email_outreach: bool = False,
        dry_run: bool = False,
        headless: bool = True
    ):
        self.llm_provider = llm_provider
        self.max_vendors_per_product = max_vendors_per_product
        self.submit_to_thomasnet = submit_to_thomasnet
        self.email_outreach = email_outreach
        self.dry_run = dry_run
        self.headless = headless

        # Initialize components
        self.db = DatabaseManager()
        self.sam_agent = None
        self.attachment_reader = None
        self.thomasnet_auth = None
        self.thomasnet_search = None
        self.rfq_parser = RFQParser()
        self.email_sender = EmailSender() if email_outreach else None

        # Set LLM provider
        config.LLM_PROVIDER = llm_provider

        logger.info(f"Pipeline initialized: LLM={llm_provider}, ThomasNet={submit_to_thomasnet}, Email={email_outreach}, DryRun={dry_run}")

    def __enter__(self):
        """Context manager entry - start browser sessions."""
        self.sam_agent = SamGovAgent()
        self.sam_agent.start_browser()
        self.attachment_reader = AttachmentReaderAgent()

        if self.submit_to_thomasnet or self.email_outreach:
            self.thomasnet_auth = ThomasNetAuth(headless=self.headless)
            self.thomasnet_auth.__enter__()  # Start browser
            self.thomasnet_search = ThomasNetSearch(self.thomasnet_auth)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup."""
        if self.sam_agent:
            self.sam_agent.close()
        if self.thomasnet_auth:
            self.thomasnet_auth.__exit__(exc_type, exc_val, exc_tb)

    def run_scheduled(self, interval_hours: int = 3, keywords: Optional[List[str]] = None):
        """Run pipeline on a schedule."""
        keywords = keywords or config.SEARCH_KEYWORDS
        logger.info(f"Starting scheduled pipeline every {interval_hours} hours with keywords: {keywords}")

        def job():
            logger.info("=== Scheduled Pipeline Run ===")
            try:
                self.run_keyword_batch(keywords)
            except Exception as e:
                logger.error(f"Scheduled job failed: {e}")

        # Run once immediately
        job()

        # Schedule recurring
        schedule.every(interval_hours).hours.do(job)

        logger.info("Scheduler active. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")

    def run_keyword_batch(self, keywords: List[str], max_solicitations_per_keyword: int = 10):
        """Run pipeline for multiple keywords."""
        for keyword in keywords:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing keyword: {keyword}")
            logger.info(f"{'='*60}")

            try:
                self.run_single_keyword(keyword, max_solicitations_per_keyword)
            except Exception as e:
                logger.error(f"Keyword '{keyword}' failed: {e}")
                continue

    def run_single_keyword(self, keyword: str, max_solicitations: int = 10):
        """Process all solicitations for a single keyword."""
        # Search SAM.gov
        logger.info(f"Searching SAM.gov for: {keyword}")
        urls = self.sam_agent.search_for_links(keyword, start_page=1, num_pages=5)
        logger.info(f"Found {len(urls)} solicitation URLs")

        processed = 0
        for url in urls:
            if processed >= max_solicitations:
                break

            if "/opp/" not in url:
                continue

            try:
                logger.info(f"\n--- Processing solicitation {processed+1}/{max_solicitations} ---")
                self.process_solicitation(url)
                processed += 1
            except Exception as e:
                logger.error(f"Failed to process {url}: {e}")
                continue

        logger.info(f"Completed {processed} solicitations for keyword: {keyword}")

    def run_single_url(self, url: str):
        """Process a single SAM.gov URL directly."""
        logger.info(f"Processing single URL: {url}")
        self.process_solicitation(url)

    def process_solicitation(self, url: str):
        """
        Complete processing pipeline for one solicitation:
        1. Scrape SAM.gov detail page + attachments
        2. Generate RFQ document
        3. Parse products from RFQ
        4. Search ThomasNet for vendors
        5. Submit via ThomasNet AND/OR email outreach
        """
        contract_id = None

        try:
            # ============ STEP 1: SCRAPE SAM.GOV ============
            logger.info(f"[1/5] Scraping SAM.gov: {url}")
            solicitation_data = self.sam_agent.process_detail_page(url)

            if not solicitation_data:
                logger.warning(f"Failed to scrape solicitation data from {url}")
                return

            contract_id = solicitation_data.get('contract_id')
            logger.info(f"Contract ID: {contract_id}")

            # Save to database
            self.db.add_solicitation(
                contract_id=contract_id,
                url=url,
                title=solicitation_data.get('title'),
                description=solicitation_data.get('description'),
                location="USA",
                product_requirements=None,
                analysis_summary=None,
                data=json.dumps(solicitation_data)
            )

            # ============ STEP 2: GENERATE RFQ ============
            logger.info(f"[2/5] Generating RFQ for {contract_id}")

            result = self.attachment_reader.create_summary_report(
                contract_id,
                skip_json=True,
                strict_fidelity=True,
                enable_self_healing=True,
                max_healing_iterations=3
            )

            if "error" in result:
                if result.get("skipped"):
                    logger.info(f"[SKIP] {contract_id}: {result['error']}")
                    return
                logger.error(f"RFQ generation failed: {result['error']}")
                return

            rfq_content = result.get("rfq_content")
            rfq_type = result.get("rfq_type", "UNKNOWN")

            if not rfq_content:
                logger.error("No RFQ content generated")
                return

            # Save RFQ to database
            self.db.add_rfq_output(contract_id, rfq_type, rfq_content, format="markdown")

            # Save as DOCX
            output_dir = os.path.join("rfq_downloads", datetime.now().strftime("%Y-%m-%d"))
            os.makedirs(output_dir, exist_ok=True)
            docx_filename = f"{contract_id}_RFQ_{rfq_type}.docx"
            docx_path = os.path.join(output_dir, docx_filename)

            logger.info(f"Converting RFQ to DOCX...")
            saved_docx = convert_md_to_docx(rfq_content, docx_path)

            if not saved_docx:
                # Fallback to markdown
                docx_path = docx_path.replace(".docx", ".md")
                with open(docx_path, "w", encoding="utf-8") as f:
                    f.write(rfq_content)
                logger.warning(f"Saved as markdown fallback: {docx_path}")

            logger.info(f"RFQ saved: {docx_path} ({len(rfq_content)} chars)")

            # ============ STEP 3: PARSE PRODUCTS FROM RFQ ============
            logger.info(f"[3/5] Parsing products from RFQ...")
            parsed_data = self.rfq_parser.parse_file(docx_path)
            products = parsed_data.get("products", [])
            metadata = parsed_data.get("metadata", {})

            if not products:
                logger.warning("No products found in RFQ, skipping vendor search")
                return

            logger.info(f"Found {len(products)} product(s): {[p['name'] for p in products]}")

            # Save products to database
            for product in products:
                self.db.add_product(
                    contract_id=contract_id,
                    product_name=product['name'],
                    description=product.get('specifications', {}).get('Description', ''),
                    specifications=json.dumps(product.get('specifications', {})),
                    quantity=product.get('quantity', 1)
                )

            # ============ STEP 4: SEARCH THOMASNET FOR VENDORS ============
            all_vendors = []

            if self.submit_to_thomasnet or self.email_outreach:
                for product in products:
                    product_name = product['name']
                    logger.info(f"[4/5] Searching ThomasNet for: {product_name}")

                    try:
                        vendors = self.thomasnet_search.search_vendors(
                            product_name,
                            max_results=self.max_vendors_per_product
                        )
                        logger.info(f"Found {len(vendors)} vendors for {product_name}")

                        # Add product context to vendors
                        for v in vendors:
                            v['product_searched'] = product_name
                            v['product_quantity'] = product.get('quantity', 1)
                            v['product_specifications'] = product.get('specifications', {})

                        all_vendors.extend(vendors)

                    except Exception as e:
                        logger.error(f"ThomasNet search failed for {product_name}: {e}")

            if not all_vendors:
                logger.warning("No vendors found, skipping submission/outreach")
                return

            # ============ STEP 5: SUBMIT RFQ / EMAIL OUTREACH ============
            logger.info(f"[5/5] Processing {len(all_vendors)} vendors...")

            # ThomasNet Batch Submission
            if self.submit_to_thomasnet:
                self._submit_via_thomasnet(all_vendors, contract_id, rfq_type, docx_path, products)

            # Direct Email Outreach
            if self.email_outreach and self.email_sender:
                self._email_outreach(all_vendors, contract_id, rfq_type, rfq_content, docx_path, products)

            logger.info(f"=== Completed processing {contract_id} ===")

        except Exception as e:
            logger.error(f"Pipeline failed for {url}: {e}")
            import traceback
            traceback.print_exc()

    def _submit_via_thomasnet(
        self,
        vendors: List[Dict[str, Any]],
        contract_id: str,
        rfq_type: str,
        rfq_file_path: str,
        products: List[Dict[str, Any]]
    ):
        """Submit RFQ via ThomasNet batch system."""
        logger.info(f"Submitting RFQ to ThomasNet for {len(vendors)} vendors...")

        if self.dry_run:
            logger.info("[DRY RUN] Would submit to ThomasNet")
            return

        try:
            # Use ThomasNetAgent for batch submission
            agent = ThomasNetAgent()

            # Prepare product data for submission
            # Use first product as primary (ThomasNet agent searches by single product)
            primary_product = products[0] if products else {"product_name": "Unknown"}

            # The agent's select_vendors_and_submit_rfq handles the full workflow
            result = agent.select_vendors_and_submit_rfq(
                product=primary_product,
                limit=self.max_vendors_per_product,
                attachment_file_path=rfq_file_path
            )

            if result.get('success'):
                logger.info(f"✓ ThomasNet submission successful: {result.get('vendors_contacted')} vendors contacted")
                logger.info(f"Confirmation: {result.get('confirmation_message')}")

                # Log to database
                for i in range(result.get('vendors_contacted', 0)):
                    self.db.add_thomasnet_submission(
                        contract_id=contract_id,
                        vendor_name=f"Vendor {i+1}",
                        vendor_company=f"ThomasNet Supplier {i+1}",
                        vendor_location="Unknown",
                        product_searched=primary_product.get('product_name', ''),
                        rfq_file_path=rfq_file_path,
                        success=True,
                        error_message=None
                    )
            else:
                logger.error(f"ThomasNet submission failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"ThomasNet submission error: {e}")

    def _email_outreach(
        self,
        vendors: List[Dict[str, Any]],
        contract_id: str,
        rfq_type: str,
        rfq_content: str,
        rfq_file_path: str,
        products: List[Dict[str, Any]]
    ):
        """Send RFQ emails directly to vendor contacts."""
        logger.info(f"Starting email outreach to {len(vendors)} vendors...")

        # Extract emails from vendor websites
        logger.info("Extracting vendor email addresses...")
        contacts = extract_vendor_emails(vendors, self.thomasnet_auth.page, max_vendors=20)

        # Filter to only vendors with emails
        email_contacts = [c for c in contacts if c.email]
        logger.info(f"Found emails for {len(email_contacts)}/{len(contacts)} vendors")

        if not email_contacts:
            logger.warning("No vendor emails found, skipping email outreach")
            return

        # Prepare contact list for email sender
        contact_list = []
        for contact in email_contacts:
            # Find matching vendor for product context
            vendor_match = next((v for v in vendors if v['name'] == contact.name), {})
            contact_list.append({
                'email': contact.email,
                'name': contact.name,
                'website': contact.website,
                'product_searched': vendor_match.get('product_searched', ''),
                'confidence': contact.confidence,
                'source': contact.source
            })

        # Send emails
        logger.info(f"Sending RFQ emails to {len(contact_list)} vendors...")
        results = self.email_sender.send_bulk_rfq(
            contacts=contact_list,
            rfq_content=rfq_content,
            rfq_type=rfq_type,
            attachment_path=rfq_file_path if os.path.exists(rfq_file_path) else None
        )

        # Log results
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        logger.info(f"Email outreach complete: {successful} sent, {failed} failed")

        for result in results:
            if not result.success:
                logger.warning(f"Failed to send to {result.recipient}: {result.error}")


def main():
    parser = argparse.ArgumentParser(description="Unified RFQ Automation Pipeline")

    # Mode selection
    parser.add_argument("--mode", choices=["keyword", "url", "scheduled"], default="keyword",
                        help="Operation mode")
    parser.add_argument("--keyword", type=str, help="Keyword to search (for keyword mode)")
    parser.add_argument("--url", type=str, help="SAM.gov URL to process (for url mode)")
    parser.add_argument("--keywords", nargs="+", help="Multiple keywords to process")

    # Pipeline options
    parser.add_argument("--max-solicitations", type=int, default=10,
                        help="Max solicitations per keyword")
    parser.add_argument("--max-vendors", type=int, default=5,
                        help="Max vendors per product")
    parser.add_argument("--llm-provider", choices=["gemini", "openai", "groq"], default="gemini",
                        help="LLM provider for RFQ generation")

    # Output options
    parser.add_argument("--submit-thomasnet", action="store_true",
                        help="Submit RFQs via ThomasNet batch system")
    parser.add_argument("--email-outreach", action="store_true",
                        help="Send RFQs via direct email to vendors")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without actual submissions")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="Run browsers in headless mode")

    # Scheduling
    parser.add_argument("--hours", type=int, default=3,
                        help="Interval hours for scheduled mode")

    args = parser.parse_args()

    # Validate
    if not args.submit_thomasnet and not args.email_outreach:
        logger.warning("Neither --submit-thomasnet nor --email-outreach enabled. Running in analysis-only mode.")

    # Run pipeline
    with UnifiedPipeline(
        llm_provider=args.llm_provider,
        max_vendors_per_product=args.max_vendors,
        submit_to_thomasnet=args.submit_thomasnet,
        email_outreach=args.email_outreach,
        dry_run=args.dry_run,
        headless=args.headless
    ) as pipeline:

        if args.mode == "scheduled":
            keywords = args.keywords or config.SEARCH_KEYWORDS
            pipeline.run_scheduled(interval_hours=args.hours, keywords=keywords)

        elif args.mode == "url":
            if not args.url:
                parser.error("--url required for url mode")
            pipeline.run_single_url(args.url)

        else:  # keyword mode
            keywords = args.keywords or ([args.keyword] if args.keyword else config.SEARCH_KEYWORDS)
            pipeline.run_keyword_batch(keywords, max_solicitations_per_keyword=args.max_solicitations)


if __name__ == "__main__":
    main()