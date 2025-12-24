
import sys
import os
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent

URL = "https://sam.gov/workspace/contract/opp/194dd9f385ab4f18bb8b05ea4c892bbc/view"
CONTRACT_ID = "8459d47ae9" # From DB

logging.basicConfig(level=logging.INFO)

def main():
    print(f"Starting Deep Fetch for Vortex: {URL}")
    agent = SamGovAgent()
    try:
        # 1. Search & Scrape
        # The URL in DB was dead. We search for the ID directly.
        KEYWORD = "N0016425SC001"
        print(f"Searching for active solicitation: {KEYWORD}")
        results = agent.search_and_scrape(KEYWORD, start_date=None)
        
        # search_and_scrape returns a list of processed results
        if results:
             print(f"Found {len(results)} results.")
             for res in results:
                 c_id = res.get('contract_id')
                 print(f"Scraped ID: {c_id}")
                 
                 # Analyze each found result
                 reader = AttachmentReaderAgent()
                 summary = reader.create_summary_report(c_id)
                 import json
                 print(json.dumps(summary, indent=2))
        else:
             print("Search returned no results.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        agent.close()

if __name__ == "__main__":
    main()
