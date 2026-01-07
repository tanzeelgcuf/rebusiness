import os
import sys
import json
import time
import schedule
import logging

# Add path to import ai_agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

import config
from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

KEYWORD_CHECKPOINT_FILE = "keyword_checkpoint.json"

def process_single_url(url, db_manager, scraper):
    """
    Runs the modern extraction pipeline on a single URL.
    Scrape -> Deep Crawl -> Download -> Vision Extract -> DB Save -> RFQ Gen -> DOCX Save
    """
    logger.info(f"Processing URL: {url}")
    
    # 1. Scrape & Download (Deep Crawl using SamGovAgent)
    try:
        logger.info(f"  Scraping detail page with SamGovAgent (Deep Fetch)...")
        solicitation_data = scraper.process_detail_page(url)
        
        if not solicitation_data:
            logger.warning(f"Failed to scrape solicitation data from {url}")
            return

        contract_id = solicitation_data.get('contract_id')
        logger.info(f"  Contract ID: {contract_id}")

        # 2. Save Basic Solicitation Info to DB
        db_manager.add_solicitation(
            contract_id=contract_id,
            url=url,
            title=solicitation_data.get('title'),
            description=solicitation_data.get('description'),
            location="USA", 
            product_requirements=None,
            analysis_summary=None,
            data=json.dumps(solicitation_data)
        )
        logger.info(f"  Saved basic info for {contract_id} to DB.")

        # 3. Extract Products & Generate RFQ (Direct Markdown)
        reader = AttachmentReaderAgent()
        logger.info(f"  Running AI Analysis & RFQ Generation...")
        
        result = reader.create_summary_report(contract_id, skip_json=True, strict_fidelity=True)
        
        if "error" in result:
            logger.error(f"  Extraction/Analysis failed for {contract_id}: {result['error']}")
        else:
            rfq_content = result.get("rfq_content")
            rfq_type = result.get("rfq_type", "UNKNOWN")
            
            if rfq_content:
                # 4. Store the high-fidelity RFQ in DB
                db_manager.add_rfq_output(contract_id, rfq_type, rfq_content, format=config.RFQ_OUTPUT_FORMAT)
                logger.info(f"  Success! RFQ Generated ({rfq_type}) and saved to DB.")
                
                # 5. Save as .docx file
                filename = f"{contract_id}_RFQ_{rfq_type}.docx"
                output_path = os.path.join("rfq_outputs", filename)
                os.makedirs("rfq_outputs", exist_ok=True)
                
                # Convert Markdown to DOCX
                from utils.doc_converter import convert_md_to_docx
                if convert_md_to_docx(rfq_content, output_path):
                    logger.info(f"  Saved RFQ DOCX to: {output_path}")
                else:
                    # Fallback to Markdown
                    md_path = output_path.replace(".docx", ".md")
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(rfq_content)
                    logger.warning(f"  DOCX conversion failed. Saved as MD: {md_path}")

            else:
                logger.error(f"  No RFQ content returned for {contract_id}")

    except Exception as e:
        logger.error(f"Scraper failed for {url}: {e}")
    # Do NOT close scraper here, it is owned by caller.

import argparse

def main_job(target_keyword=None, force_start_page=None, force_num_pages=None):
    """
    Main Loop: Rotate Keywords -> Search -> Extract
    Args:
        target_keyword: If set, only scrape this keyword.
        force_start_page: If set, start at this page.
        force_num_pages: If set, scrape this many pages (overrides batch default).
    """
    logger.info("\n=== STARTING JOB ===")
    
    db_manager = DatabaseManager()
    sam_agent = SamGovAgent()
    sam_agent.start_browser()
    
    try:
        # 1. Configuration & State Management
        PAGES_PER_BATCH = 10
        current_state = {'keyword_index': 0, 'page_offset': 1}
        
        # Load state ONLY if not forced by CLI args
        if not target_keyword and os.path.exists(KEYWORD_CHECKPOINT_FILE):
            try:
                with open(KEYWORD_CHECKPOINT_FILE, 'r') as f:
                    current_state = json.load(f)
            except json.JSONDecodeError: pass
            
        keyword_index = current_state.get('keyword_index', 0)
        
        # Determine WHAT to search
        if target_keyword:
            scan_keyword = target_keyword
            start_page = force_start_page if force_start_page else 1
            num_pages = force_num_pages if force_num_pages else PAGES_PER_BATCH  # Default to 10 if not specified
            logger.info(f"*** MANUAL OVERRIDE: Scraping '{scan_keyword}' from Page {start_page} len {num_pages} ***")
        else:
            # Standard Batch Logic
            keywords = config.SEARCH_KEYWORDS
            if not keywords:
                logger.warning("No search keywords defined in config.py!")
                return
            if keyword_index >= len(keywords):
                keyword_index = 0
            
            scan_keyword = keywords[keyword_index]
            start_page = current_state.get('page_offset', 1)
            num_pages = PAGES_PER_BATCH
            logger.info(f"--- BATCH JOB: '{scan_keyword}' | Pages {start_page} to {start_page + num_pages - 1} ---")

        # 2. Find URLs (using SamGovAgent with offset)
        found_urls = sam_agent.search_for_links(scan_keyword, start_page=start_page, num_pages=num_pages)
        logger.info(f"Found {len(found_urls)} URLs.")
        
        # 3. Process URLs
        for url in found_urls:
            if "/opp/" not in url: continue
            process_single_url(url, db_manager, sam_agent)

        # 4. State Update (Only for scheduled batches)
        if not target_keyword:
            if not found_urls:
                # If no results (end of list), move to next keyword and reset page
                logger.info("  > No more results for this keyword. Rotating...")
                next_keyword_index = (keyword_index + 1) % len(keywords)
                next_page = 1
            else:
                # Continue deeper next time
                next_keyword_index = keyword_index
                next_page = start_page + PAGES_PER_BATCH
                
            with open(KEYWORD_CHECKPOINT_FILE, 'w') as f:
                json.dump({'keyword_index': next_keyword_index, 'page_offset': next_page}, f)

    except Exception as e:
        logger.error(f"CRITICAL JOB ERROR: {e}")
    finally:
        sam_agent.close()
        logger.info("=== JOB FINISHED ===")

def process_extract_and_generate_rfq(url, args):
    """
    Directly extracts solicitation data and generates a high-fidelity RFQ.
    """
    logger.info(f"=== Extract and Generate RFQ Mode ===")
    logger.info(f"URL: {url}")
    
    db_manager = DatabaseManager()
    sam_agent = SamGovAgent()
    sam_agent.start_browser()
    
    try:
        # 1. Scrape & Download (Aggressive crawl if specified)
        logger.info(f"Scraping with SamGovAgent...")
        solicitation_data = sam_agent.process_detail_page(url)
        
        if not solicitation_data:
            logger.error("Failed to scrape solicitation data.")
            return

        contract_id = solicitation_data.get('contract_id')
        logger.info(f"Contract ID: {contract_id}")

        # Ensure solicitation is in DB
        db_manager.add_solicitation(
            contract_id=contract_id,
            url=url,
            title=solicitation_data.get('title'),
            description=solicitation_data.get('description'),
            location="USA",
            product_requirements=None,
            analysis_summary=None,
            data=json.dumps(solicitation_data)
        )

        # 2. Extract and Generate
        reader = AttachmentReaderAgent()
        logger.info(f"Running high-fidelity extraction and RFQ generation...")
        
        # Use new logic in AttachmentReaderAgent
        result = reader.create_summary_report(
            contract_id,
            skip_json=True, # Always skip JSON for this mode
            strict_fidelity=args.strict_fidelity,
            template_type=args.template_type,
            internal_deadline_offset=args.internal_deadline_offset,
            vendor_email=args.vendor_email,
            organization_name=args.organization_name
        )
        
        if "error" in result:
            logger.error(f"Generation failed: {result['error']}")
        else:
            # Result is dict {"rfq_content": ..., "rfq_type": ...}
            rfq_content = result.get("rfq_content")
            rfq_type = result.get("rfq_type", "UNKNOWN")
            
            if rfq_content:
                # Save to DB first
                # Note: config.RFQ_OUTPUT_FORMAT drives the stored format meta, but we store raw content usually
                db_manager.add_rfq_output(contract_id, rfq_type, rfq_content, format=config.RFQ_OUTPUT_FORMAT)
                
                # Save to file
                output_filename = f"{contract_id}_RFQ_{rfq_type}.{config.RFQ_OUTPUT_FORMAT}"
                output_path = os.path.join(os.getcwd(), output_filename)
                
                if config.RFQ_OUTPUT_FORMAT == "docx":
                    from utils.doc_converter import convert_md_to_docx
                    if convert_md_to_docx(rfq_content, output_path):
                         logger.info(f"Success! RFQ ({rfq_type}) saved to {output_filename} and DB.")
                    else:
                         logger.error(f"Failed to save DOCX to {output_filename}")
                else:
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(rfq_content)
                    logger.info(f"Success! RFQ ({rfq_type}) saved to {output_filename} and DB.")
            else:
                logger.error("No RFQ content returned.")

    except Exception as e:
        logger.error(f"Failed to process: {e}")
    finally:
        sam_agent.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAM.gov Scraper Workflow")
    parser.add_argument("--mode", type=str, default="default", help="Operation mode (e.g., 'extract-and-generate-rfq')")
    parser.add_argument("--url", type=str, help="SAM.gov URL for direct processing")
    parser.add_argument("--keyword", type=str, help="Override keyword to scrape")
    parser.add_argument("--page", type=int, help="Start page number")
    parser.add_argument("--pages", type=int, help="Number of pages to scrape")
    parser.add_argument("--loop", action="store_true", help="Run in continuous schedule loop")
    
    # New flags for RFQ generation
    parser.add_argument("--aggressive-crawl", action="store_true", help="Deep crawl all attachments")
    parser.add_argument("--skip-json", action="store_true", help="Direct markdown generation")
    parser.add_argument("--output-format", type=str, default="markdown", help="Output format (markdown)")
    parser.add_argument("--template-type", type=str, default="auto-detect", help="PRODUCT or SERVICE")
    parser.add_argument("--strict-fidelity", action="store_true", help="Zero-placeholder policy")
    parser.add_argument("--internal-deadline-offset", type=int, default=4, help="Business days before official")
    parser.add_argument("--vendor-email", type=str, default="john@campsable.com", help="Vendor contact email")
    parser.add_argument("--organization-name", type=str, default="Camp Sable, LLC", help="Organization name")
    
    args = parser.parse_args()

    if args.mode == "extract-and-generate-rfq":
        if not args.url:
            print("Error: --url is required for extract-and-generate-rfq mode.")
            sys.exit(1)
        process_extract_and_generate_rfq(args.url, args)
    elif args.keyword:
        # Manual Run
        main_job(target_keyword=args.keyword, force_start_page=args.page, force_num_pages=args.pages)
    elif args.loop:
        # Scheduled Service Mode
        logger.info("Service Started. Running initial job...")
        main_job() # Initial run
        
        schedule.every(3).hours.do(main_job)
        logger.info("Scheduler Active (Every 3 Hours). Press Ctrl+C to exit.")
        while True:
            schedule.run_pending()
            time.sleep(1)
    else:
        # Default behavior: Just run one batch Job
        main_job()