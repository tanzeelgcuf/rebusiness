import csv
import os
import sys
import logging
import time
import json

# Add ai_agents path
sys.path.append(os.path.abspath('ai_agents'))

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager

LEADS_FILE = "leads.csv"
SOLICITATIONS_FILE = "solicitations.json"
LOG_FILE = "extraction_log.txt"

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(LOG_FILE),
                        logging.StreamHandler(sys.stdout)
                    ])
logger = logging.getLogger()

def main():
    logger.info("--- Starting Batch Extraction Pipeline ---")
    
    if not os.path.exists(LEADS_FILE):
        logger.error(f"Leads file {LEADS_FILE} not found.")
        return

    db_manager = DatabaseManager()
    
    # Initialize Agents
    # Note: Headless=True for batch processing
    # Initialize Agents
    # SamGovAgent handles browsing natively (Playwright)
    downloader = SamGovAgent()
    reader = AttachmentReaderAgent()

    # Load Solicitations
    solicitation_urls = []
    
    # Try reading JSON first
    if os.path.exists(SOLICITATIONS_FILE):
        try:
            with open(SOLICITATIONS_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
                    if isinstance(data, list):
                        solicitation_urls = [url for url in data if isinstance(url, str) and url.startswith("http")]
                    elif isinstance(data, dict):
                         # Handle if it's a dict like {"urls": [...]} or similar, though list is expected
                         pass
        except json.JSONDecodeError:
            logger.warning(f"{SOLICITATIONS_FILE} was not valid JSON.")

    if not solicitation_urls:
        logger.info(f"{SOLICITATIONS_FILE} is empty or missing. Populating from {LEADS_FILE}...")
        if os.path.exists(LEADS_FILE):
            leads = []
            with open(LEADS_FILE, 'r', encoding='utf-8', errors='replace') as f:
                reader_csv = csv.DictReader(f)
                leads = list(reader_csv)
            
            unique_urls = set()
            for lead in leads:
                url = lead.get("SAM.gov Link")
                if url and "sam.gov" in url:
                    unique_urls.add(url)
            
            solicitation_urls = list(unique_urls)
            
            # Save to JSON for future use
            with open(SOLICITATIONS_FILE, 'w') as f:
                json.dump(solicitation_urls, f, indent=2)
            logger.info(f"Saved {len(solicitation_urls)} URLs to {SOLICITATIONS_FILE}.")
        else:
            logger.error(f"Neither {SOLICITATIONS_FILE} nor {LEADS_FILE} found.")
            return

    logger.info(f"Found {len(solicitation_urls)} unique SAM.gov URLs to process.")

    processed_count = 0
    error_count = 0

    try:
        for i, url in enumerate(solicitation_urls):
            if "sam.gov" not in url or "/opp/" not in url:
                logger.warning(f"Skipping invalid solicitation URL (must be a direct '/opp/' link): {url}")
                continue

            contract_id = url.split('/')[-1].replace("view", "").strip('/') # Simple ID extraction fallback
            if "opp" in url: 
                 # Better extraction matching the agent logic if possible, or just let agent handle it.
                 pass

            logger.info(f"Processing ({i+1}/{len(solicitation_urls)}): {url}")
            
            # Check if already exists/analyzed?
            # Ideally verify against DB, but agent has some checks. 
            # We will force run to ensure deep extraction is applied.
            
            try:
                # 1. Scrape & Download (SamGovAgent)
                # process_detail_page handles scraping, deep fetch, and deep linking internally
                # It returns the solicitation data dict.
                solicitation_data = downloader.process_detail_page(url)
                
                if not solicitation_data:
                    logger.warning(f"  Failed to process {url}")
                    error_count += 1
                    continue
                
                contract_id = solicitation_data['contract_id']
                
                # Check file count in directory
                att_dir = os.path.join("data/solicitations", contract_id, "attachments")
                file_count = len(os.listdir(att_dir)) if os.path.exists(att_dir) else 0
                logger.info(f"  Scraped {contract_id}. Files/Links Processed: {file_count}")

                # 2. Extract & Save (Gemini Vision)
                # This automatically saves to 'products' table as per my recent update
                analysis = reader.create_summary_report(contract_id)
                
                if "error" in analysis:
                    logger.error(f"  Extraction failed for {contract_id}: {analysis['error']}")
                    error_count += 1
                else:
                    prod_count = len(analysis.get('product_details', []))
                    logger.info(f"  Success! Extracted {prod_count} products for {contract_id}.")
                    processed_count += 1

            except Exception as e:
                logger.error(f"  Critical error processing {url}: {e}")
                error_count += 1
            
            # Polite delay
            time.sleep(5)

    finally:
        downloader.close()
        logger.info("--- Batch Extraction Complete ---")
        logger.info(f"Processed: {processed_count}")
        logger.info(f"Errors: {error_count}")

if __name__ == "__main__":
    main()
