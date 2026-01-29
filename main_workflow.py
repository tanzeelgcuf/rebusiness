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
try:
    from validate_rfq import RFQValidator
except ImportError:
    RFQValidator = None

# ThomasNet Import (Lazy import inside functions to avoid strict dependency on playwright if unused)
# from ai_agents.ThomasNetAgent.cli import submit_rfq_programmatic # Hypothetical function, will implement inline

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
from datetime import datetime

KEYWORD_CHECKPOINT_FILE = "keyword_checkpoint.json"

def run_thomasnet_submission(rfq_path, args):
    """
    Helper to run ThomasNet submission if enabled.
    """
    if not args.submit_to_thomasnet:
        return

    logger.info(f"🔄 [ThomasNet] Starting submission for: {rfq_path}")
    try:
        # Import here to avoid early dependency failure
        from ai_agents.ThomasNetAgent.cli import submit as thomasnet_submit_cmd
        from click.testing import CliRunner
        
        # We invoke the click command programmatically.
        # Ideally we would refactor cli.py to expose a clean python function,
        # but reusing the CLI command ensures consistent behavior.
        runner = CliRunner()
        
        # Prepare args
        cmd_args = ['--rfq', rfq_path, '--max-vendors', str(args.thomasnet_max_vendors)]
        
        if not args.thomasnet_headless:
            cmd_args.append('--no-headless')
            
        if args.thomasnet_dry_run:
            cmd_args.append('--dry-run')
            
        logger.info(f"  [ThomasNet] Invoking agent with args: {cmd_args}")
        
        # NOTE: Using standalone_mode=False to prevent system exit
        # We need to import the actual context_settings if needed, but invoke is easier
        # Direct function call if decorated with click is tricky.
        # Better approach: Refactor CLI to call a service function. 
        # For now, we'll try running it via subprocess or direct call if possible.
        # Direct call to the function wrapped by click requires Context.
        
        # Let's use subprocess for maximum isolation and stability
        import subprocess
        
        cli_path = os.path.join(os.path.dirname(__file__), 'ai_agents', 'ThomasNetAgent', 'cli.py')
        python_exe = sys.executable
        
        cmd = [python_exe, cli_path, 'submit'] + cmd_args
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            logger.info(f"  [ThomasNet] Submission process completed successfully.")
            logger.debug(f"  Output: {process.stdout}")
        else:
            logger.error(f"  [ThomasNet] Submission process failed with code {process.returncode}")
            logger.error(f"  Stderr: {process.stderr}")

    except Exception as e:
        logger.error(f"  [ThomasNet] Error triggering submission: {e}")


def process_single_url(url, db_manager, scraper, args=None):
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
        
        result = reader.create_summary_report(
            contract_id, 
            skip_json=True, 
            strict_fidelity=True,
            enable_self_healing=True,
            max_healing_iterations=3
        )
        
        if "error" in result:
            logger.error(f"  [!] Extraction/Analysis failed for {contract_id}: {result['error']}")
        else:
            rfq_content = result.get("rfq_content")
            rfq_type = result.get("rfq_type", "UNKNOWN")
            
            if rfq_content:
                # 4. Store the high-fidelity RFQ in DB
                db_manager.add_rfq_output(contract_id, rfq_type, rfq_content, format="docx")
                logger.info(f"  [+] RFQ Content Generated ({rfq_type} | {len(rfq_content)} chars)")
                
                # 5. Save as .docx file (PRIMARY FORMAT)
                filename = f"{contract_id}_RFQ_{rfq_type}.docx"
                output_dir = os.path.join("rfq_downloads", datetime.now().strftime("%Y-%m-%d"))
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, filename)
                
                logger.info(f"  [>] Converting to DOCX...")
                from utils.doc_converter import convert_md_to_docx
                
                saved_docx = convert_md_to_docx(rfq_content, output_path)
                
                if saved_docx:
                    logger.info(f"  [SUCCESS] Saved DOCX: {output_path}")
                else:
                    # Fallback to Markdown
                    md_path = output_path.replace(".docx", ".md")
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(rfq_content)
                    logger.warning(f"  [FALLBACK] DOCX conversion failed. Saved as MD: {md_path}")
                
                # 6. Validate RFQ
                final_validation_score = 0
                if RFQValidator:
                    logger.info(f"  [>] Validating RFQ Quality...")
                    validator = RFQValidator(rfq_type)
                    val_result = validator.validate_from_docx(output_path)
                    val_score = val_result['score']
                    final_validation_score = val_score
                    val_report = validator.generate_report(val_result, output_path.replace('.docx', '_validation_report.txt'))
                    logger.info(f"  [VALIDATION] Score: {val_score}/100. Status: {val_result['status']}")
                    
                    # Log warning if score is low
                    if val_score < 95:
                        logger.warning(f"  [!] QA Alert: RFQ score {val_score}/100 is below 95 threshold.")
                    if val_result['issues']:
                        logger.warning(f"  [!] Issues: {val_result['issues']}")

                # 7. ThomasNet Submission (Integrated Step)
                if args and args.submit_to_thomasnet and saved_docx:
                    if final_validation_score >= 80: # Safety quality gate
                        run_thomasnet_submission(output_path, args)
                    else:
                        logger.warning(f"  [ThomasNet] Skipping submission due to low validation score ({final_validation_score})")

            else:
                logger.error(f"  [!] No RFQ content returned for {contract_id}")

    except Exception as e:
        logger.error(f"Scraper failed for {url}: {e}")
    # Do NOT close scraper here, it is owned by caller.

import argparse

def main_job(target_keyword=None, force_start_page=None, force_num_pages=None, args=None):
    """
    Main Loop: Rotate Keywords -> Search -> Extract
    Args:
        target_keyword: If set, only scrape this keyword.
        force_start_page: If set, start at this page.
        force_num_pages: If set, scrape this many pages (overrides batch default).
        args: Parsed CLI arguments
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
            process_single_url(url, db_manager, sam_agent, args=args)

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
            organization_name=args.organization_name,
            enable_self_healing=not args.no_self_healing,
            max_healing_iterations=args.max_healing_iterations
        )
        
        if "error" in result:
            if result.get("skipped"):
                logger.info(f"[SKIP] {contract_id} skipped: {result['error']}")
                return # Stop processing this URL
            logger.error(f"  [!] Generation failed for {contract_id}: {result['error']}")
        else:
            # Result is dict {"rfq_content": ..., "rfq_type": ...}
            rfq_content = result.get("rfq_content")
            rfq_type = result.get("rfq_type", "UNKNOWN")
            
            if rfq_content:
                # Save to DB first
                # Note: config.RFQ_OUTPUT_FORMAT drives the stored format meta, but we store raw content usually
                db_manager.add_rfq_output(contract_id, rfq_type, rfq_content, format="docx")
                
                # Save to file
                filename = f"{contract_id}_RFQ_{rfq_type}.docx"
                output_dir = os.path.join("rfq_downloads", datetime.now().strftime("%Y-%m-%d"))
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, filename)
                
                logger.info(f"  [>] Converting to DOCX...")
                from utils.doc_converter import convert_md_to_docx
                
                saved_docx = convert_md_to_docx(rfq_content, output_path)
                
                if saved_docx:
                     logger.info(f"  [SUCCESS] RFQ ({rfq_type}) saved to {output_path} and DB.")
                     
                     # 3. Post-Generation Validation (if enabled)
                     logger.info(f"  [>] Validating RFQ Quality...")
                     from validate_rfq import RFQValidator
                     validator = RFQValidator(rfq_type)
                     val_result = validator.validate_from_docx(output_path)
                     
                     report_path = output_path.replace('.docx', '_validation_report.txt')
                     validator.generate_report(val_result, report_path)
                     
                     logger.info(f"  [VALIDATION] Score: {val_result['score']}/100. Report saved to {report_path}")

                     if val_result['issues']:
                         logger.warning(f"  Issues found: {len(val_result['issues'])}")
                         for issue in val_result['issues'][:3]:
                             logger.warning(f"    - {issue}")
                     
                     # 4. ThomasNet Submission
                     if args.submit_to_thomasnet:
                         if val_result['score'] >= 80:
                             run_thomasnet_submission(output_path, args)
                         else:
                             logger.warning(f"  [ThomasNet] Skipping submission due to low validation score ({val_result['score']})")

                else:
                     # Fallback
                     md_path = output_path.replace(".docx", ".md")
                     with open(md_path, "w", encoding="utf-8") as f:
                         f.write(rfq_content)
                     logger.warning(f"  [FALLBACK] Failed to save DOCX. Saved MD to {md_path}")
            else:
                logger.error("  [!] No RFQ content returned.")

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
    
    # Self-healing QA flags
    parser.add_argument("--no-self-healing", action="store_true", help="Disable self-healing QA (faster but may have quality issues)")
    parser.add_argument("--max-healing-iterations", type=int, default=3, help="Maximum self-healing attempts (default: 3)")
    
    # ThomasNet Automation Flags
    parser.add_argument("--submit-to-thomasnet", action="store_true", help="Auto-submit generated RFQs to ThomasNet vendors")
    parser.add_argument("--thomasnet-dry-run", action="store_true", help="Run ThomasNet in dry-run mode (no actual submission)")
    parser.add_argument("--thomasnet-max-vendors", type=int, default=5, help="Max vendors per product (default: 5)")
    parser.add_argument("--thomasnet-headless", action="store_true", default=True, help="Run ThomasNet browser in headless mode")
    
    args = parser.parse_args()

    if args.mode == "extract-and-generate-rfq":
        if not args.url:
            print("Error: --url is required for extract-and-generate-rfq mode.")
            sys.exit(1)
        process_extract_and_generate_rfq(args.url, args)
    elif args.keyword:
        # Manual Run
        main_job(target_keyword=args.keyword, force_start_page=args.page, force_num_pages=args.pages, args=args)
    elif args.loop:
        # Scheduled Service Mode
        logger.info("Service Started. Running initial job...")
        main_job(args=args) # Initial run
        
        schedule.every(3).hours.do(lambda: main_job(args=args))
        logger.info("Scheduler Active (Every 3 Hours). Press Ctrl+C to exit.")
        while True:
            schedule.run_pending()
            time.sleep(1)
    else:
        # Default behavior: Just run one batch Job
        main_job(args=args)