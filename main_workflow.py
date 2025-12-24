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
    Scrape -> Deep Crawl -> Download -> Vision Extract -> DB Save
    """
    logger.info(f"Processing URL: {url}")
    
    # 1. Scrape & Download (Deep Crawl using SamGovAgent)
    # We reuse the passed scraper instance (SamGovAgent) to keep the same Playwright context.
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

        # 3. Extract Products with Gemini Vision (Deep Analysis)
        reader = AttachmentReaderAgent()
        logger.info(f"  Running AI Analysis on downloaded files...")
        analysis = reader.create_summary_report(contract_id)
        
        if "error" in analysis:
            logger.error(f"  Extraction/Analysis failed for {contract_id}: {analysis['error']}")
        else:
            db_manager.add_solicitation_analysis(contract_id, json.dumps(analysis))
            prod_count = len(analysis.get('product_details', []))
            logger.info(f"  Success! Extracted {prod_count} products for {contract_id}.")

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAM.gov Scraper Workflow")
    parser.add_argument("--keyword", type=str, help="Override keyword to scrape (e.g., 'product')")
    parser.add_argument("--page", type=int, help="Start page number (default: 1)")
    parser.add_argument("--pages", type=int, help="Number of pages to scrape (default: 10)")
    parser.add_argument("--loop", action="store_true", help="Run in continuous schedule loop (standard mode)")
    
    args = parser.parse_args()

    if args.keyword:
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
        # Default behavior: Just run one batch Job (useful for testing/cron)
        main_job()