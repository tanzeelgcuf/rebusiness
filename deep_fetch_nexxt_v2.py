
import sys
import os
import json
import logging
from playwright.sync_api import sync_playwright

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent

# We need to search for the Justification or Original Solicitation
KEYWORD = "36C26126AP1866" 
URL = "https://sam.gov/workspace/contract/opp/1a5c9c24027047688641b4a08412ea45/view"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

def main():
    logger.info(f"Starting Expanded Deep Fetch for: {KEYWORD}")
    
    agent = SamGovAgent()
    try:
        # 1. Search for related docs
        # Force full search (ignore date)
        logger.info(f"Searching for related solicitations/docs with term '{KEYWORD}'...")
        # We call search_and_scrape directly to bypass checkpoint logic in search_for_new_solicitations
        results = agent.search_and_scrape(KEYWORD, start_date=None)
        
        found_target = False
        target_dir = None
        
        for res in results:
             print(f"Found: {res['title']} - {res['url']}")
             # We want to check attachments of ALL found related items
             # especially "J&A" or "Redacted" documents
             
             # The agent already downloads them to data/solicitations/{id}/attachments
             # Let's list what we found
             contract_id = res['contract_id']
             d = f"data/solicitations/{contract_id}/attachments"
             if os.path.exists(d):
                 files = os.listdir(d)
                 print(f"  Files in {contract_id}: {files}")
                 if files:
                     found_target = True
                     target_dir = d
        
        if not found_target:
             print("No attachments found in related searches. Trying the specific award page again with aggressive click...")
             # Re-try the specific URL with deep fetch explicitly
             res = agent.process_detail_page(URL)
             contract_id = res.get('contract_id')
             d = f"data/solicitations/{contract_id}/attachments"
             if os.path.exists(d):
                 files = os.listdir(d)
                 print(f"  Deep Fetch Result Files: {files}")
                 # Check for J&A
                 for f in files:
                     if "JA" in f or "Justification" in f:
                         print(f"  *** FOUND CRITICAL J&A DOC: {f} ***")
                         # Analyze it immediately
                         reader = AttachmentReaderAgent()
                         print("  Analyzing J&A...")
                         analysis = reader.create_summary_report(contract_id)
                         import json
                         print(json.dumps(analysis, indent=2))


    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        agent.close()

if __name__ == "__main__":
    main()
