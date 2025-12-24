
import sys
import os
import asyncio
import json
import logging

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager

# URL from DB
URL = "https://sam.gov/workspace/contract/opp/1a5c9c24027047688641b4a08412ea45/view"
CONTRACT_ID = "483f26d1ad" # From DB query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

def main():
    logger.info(f"Starting Deep Fetch for Nexxt Spine Context: {URL}")
    
    # 1. Download Attachments
    scraper = SamGovAgent()
    try:
        sol_data = scraper.process_detail_page(URL)
        if not sol_data:
            logger.error("Failed to scrape page.")
            return
        
        # We need the contract_id the scraper found to know where files are
        scraped_id = sol_data.get('contract_id')
        logger.info(f"Scraper ID: {scraped_id} (Expected roughly {CONTRACT_ID})")
        
        # 2. Analyze
        reader = AttachmentReaderAgent()
        analysis = reader.create_summary_report(scraped_id)
        
        print("\n--- ANALYSIS RESULT ---")
        print(json.dumps(analysis, indent=2))
        
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
