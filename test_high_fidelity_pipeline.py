
import os
import sys
import json
import logging
from datetime import datetime

# Setup paths
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'ai_agents'))

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.AttachmentReaderAgent.government_solicitation_processor import GovernmentSolicitationProcessor
from ai_agents.ProductProcessor.product_processor import VendorListOutputGenerator
from database_manager import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test URLs found by browser subagent
SERVICE_URL = "https://sam.gov/opp/6b3f283f01be472c852468a4539c98a8/view" # Repair Water Collectors
PRODUCT_URL = "https://sam.gov/opp/c64e568140b64169a215446d51a9500d/view" # MK22 Motor Tubes

def process_and_generate(url, mode="SERVICE"):
    print(f"\n{'='*80}")
    print(f"PROCESSING: {url} ({mode})")
    print(f"{'='*80}\n")
    
    db_manager = DatabaseManager()
    scraper = SamGovAgent()
    scraper.start_browser()
    
    try:
        # Step 1: Scrape
        print(f"Step 1: Scraping {url}...")
        data = scraper.process_detail_page(url)
        if not data:
            print("✗ Scraping failed.")
            return
        
        contract_id = data.get('contract_id')
        print(f"✓ Scraped: {data.get('title')} (ID: {contract_id})")
        
        # Save to DB for AttachmentReaderAgent to find attachments
        db_manager.add_solicitation(
            contract_id=contract_id,
            url=url,
            title=data.get('title'),
            description=data.get('description'),
            location="USA",
            product_requirements=None,
            analysis_summary=None,
            data=json.dumps(data)
        )
        
        # Step 2: Identification of Primary Attachment
        # For GovernmentSolicitationProcessor (Service/Rule-based), we need the PDF path.
        # For VendorListOutputGenerator (Product/LLM-based), we need the LLM analysis.
        
        # Step 2: High-Fidelity Extraction & Generation
        print(f"\nStep 2: Processing {mode} (LLM-based extraction)...")
        from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request
        
        reader = AttachmentReaderAgent()
        analysis = reader.create_summary_report(contract_id)
        
        if "error" in analysis:
            print(f"✗ Extraction failed: {analysis['error']}")
            return
        
        # Ensure solicitation type is set for the formatter
        analysis['solicitation_type'] = mode
        
        print("✓ Extraction successful. Generating Vendor RFQ...")
        rfq = create_bid_request(analysis)
        md_output = rfq['body']
        
        suffix = "service" if mode == "SERVICE" else "product"
        output_file = f"test_output_{contract_id}_{suffix}.md"
        with open(output_file, 'w') as f:
            f.write(md_output)
        print(f"✓ {mode} Output saved to: {output_file}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        test_mode = sys.argv[2] if len(sys.argv) > 2 else "SERVICE"
        process_and_generate(test_url, test_mode)
    else:
        # Default: Test both
        process_and_generate(SERVICE_URL, "SERVICE")
        process_and_generate(PRODUCT_URL, "PRODUCT")
