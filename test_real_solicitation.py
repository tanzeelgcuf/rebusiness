"""
Test Template Extraction on Real SAM.gov Solicitation

Tests the complete pipeline:
1. Scrape solicitation from SAM.gov
2. Extract with template-specific prompts
3. Generate template-compliant RFQ
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request
from database_manager import DatabaseManager
import json

# Test URL
TEST_URL = "https://sam.gov/opp/92341e2e45ca4323919060d2d4cfc62f/view"

def test_real_solicitation(url):
    """Test complete extraction pipeline on real solicitation"""
    print("="*80)
    print("TESTING REAL SOLICITATION")
    print("="*80)
    print(f"\nURL: {url}\n")
    
    db_manager = DatabaseManager()
    
    # Step 1: Scrape with SamGovAgent
    print("Step 1: Scraping solicitation with SamGovAgent...")
    scraper = SamGovAgent()
    scraper.start_browser()  # Initialize browser
    
    try:
        solicitation_data = scraper.process_detail_page(url)
        
        if not solicitation_data:
            print("✗ Failed to scrape solicitation")
            return
        
        contract_id = solicitation_data.get('contract_id')
        print(f"✓ Scraped successfully")
        print(f"  Contract ID: {contract_id}")
        print(f"  Title: {solicitation_data.get('title', 'N/A')}")
        
        # Save to database
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
        print(f"✓ Saved to database")
        
        # Step 2: Extract with AttachmentReaderAgent
        print("\nStep 2: Extracting with template-specific prompts...")
        reader = AttachmentReaderAgent()
        analysis = reader.create_summary_report(contract_id)
        
        if "error" in analysis:
            print(f"✗ Extraction failed: {analysis['error']}")
            return
        
        print(f"✓ Extraction successful")
        print(f"  Solicitation Type: {analysis.get('solicitation_type', 'Unknown')}")
        print(f"  Notice ID: {analysis.get('notice_id', 'N/A')}")
        
        # Save analysis
        db_manager.add_solicitation_analysis(contract_id, json.dumps(analysis))
        
        # Save to file for review
        with open('test_extraction_output.json', 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"✓ Full extraction saved to: test_extraction_output.json")
        
        # Step 3: Generate RFQ with ProposalWriter
        print("\nStep 3: Generating template-compliant RFQ...")
        rfq = create_bid_request(analysis, "Test Vendor")
        
        print(f"✓ RFQ generated")
        print(f"  Subject: {rfq['subject']}")
        
        # Save RFQ
        with open('test_rfq_output.txt', 'w') as f:
            f.write(f"Subject: {rfq['subject']}\n\n")
            f.write(rfq['body'])
        print(f"✓ RFQ saved to: test_rfq_output.txt")
        
        # Display preview
        print("\n" + "="*80)
        print("RFQ PREVIEW (first 1000 characters)")
        print("="*80)
        print(rfq['body'][:1000])
        print("\n[... see test_rfq_output.txt for full content ...]")
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"✓ Scraping: SUCCESS")
        print(f"✓ Extraction: SUCCESS")
        print(f"✓ RFQ Generation: SUCCESS")
        print(f"\nSolicitation Type: {analysis.get('solicitation_type', 'Unknown')}")
        print(f"Template Used: {'Claude Vendor List.odt' if 'PRODUCT' in analysis.get('solicitation_type', '') else 'Claude Services List.odt'}")
        print(f"\nReview files:")
        print(f"  - test_extraction_output.json (full extraction data)")
        print(f"  - test_rfq_output.txt (template-compliant RFQ)")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()

if __name__ == "__main__":
    test_real_solicitation(TEST_URL)
