import os
import sys
import json
from ai_agents.DescriptionDownloaderAgent.description_downloader_agent import DescriptionDownloaderAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager

# Target URL from leads.csv
TEST_URL = "https://sam.gov/opp/W912HZ26Q1215/view"

def main():
    print(f"--- Testing Advanced Extraction Pipeline on {TEST_URL} ---")
    
    # 1. Scrape & Download (including Deep Crawl)
    print("\n[Step 1] Running DescriptionDownloaderAgent...")
    downloader = DescriptionDownloaderAgent(headless=True)
    try:
        solicitation_data, files = downloader.scrape_and_download(TEST_URL)
    except Exception as e:
        print(f"Downloader failed: {e}")
        return
    finally:
        downloader.close()

    if not solicitation_data:
        print("Failed to scrape solicitation.")
        return

    contract_id = solicitation_data['contract_id']
    print(f"Contract ID: {contract_id}")
    print(f"Downloaded {len(files)} files.")

    # 2. Extract with Gemini Vision
    print("\n[Step 2] Running AttachmentReaderAgent (Gemini Vision)...")
    reader = AttachmentReaderAgent()
    analysis = reader.create_summary_report(contract_id)

    if "error" in analysis:
        print(f"Analysis failed: {analysis['error']}")
    else:
        print("\n[Step 3] Analysis Success!")
        print(json.dumps(analysis, indent=2))
        
        # 3. Verify Database
        print("\n[Step 4] Verifying Database Entry...")
        db = DatabaseManager()
        products = db.get_products_by_contract(contract_id)
        print(f"Found {len(products)} products in DB:")
        for p in products:
            print(f" - {p['product_name']} (Qty: {p['quantity']})")
            print(f"   Specs: {p['specifications'][:100]}...")

if __name__ == "__main__":
    main()
