
import os
import sys
from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request
from database_manager import DatabaseManager

def test_targeted_extraction():
    # 1. Scrape the specific NECO link found in the solicitation
    neco_url = "https://www.neco.navy.mil/biz_ops/840-v5soln.aspx?soln=N0010425QNF13"
    contract_id = "N0010425QNF13" # Use the explicit ID
    
    print(f"--- Starting Targeted Test for {contract_id} ---")
    
    agent = SamGovAgent()
    agent.start_browser()
    db = DatabaseManager()
    
    try:
        # We simulate the finding of the link in a solicitation
        contract_dir = agent.ensure_solicitation_directory(contract_id)
        attachment_dir = os.path.join(contract_dir, "attachments")
        if not os.path.exists(attachment_dir): os.makedirs(attachment_dir)
        
        # Run the deep crawl on the NECO URL
        print(f"Crawling NECO portal: {neco_url}")
        agent._recursive_crawl(neco_url, depth=1, max_depth=2, target_dir=attachment_dir)
        
        # Register in DB (to simulate full agent behavior)
        agent._register_attachments_in_db(contract_id, attachment_dir)
        
        # 2. Run Extraction
        print("\n--- Running AI Extraction ---")
        reader = AttachmentReaderAgent()
        # Mock a solicitation row if it doesn't exist
        db.add_solicitation(contract_id, neco_url, "REPAIR OF CABLE ASSEMBLY,SPEC", "Extracted via targeted test", "USA", None, None, "{}")
        
        analysis = reader.create_summary_report(contract_id)
        
        print("\n--- Extraction Result ---")
        import json
        print(json.dumps(analysis, indent=2))
        
        # 3. Generate RFQ
        print("\n--- Generating RFQ Output ---")
        rfq = create_bid_request(analysis)
        print("\nSUBJECT:", rfq['subject'])
        print("\nBODY:\n", rfq['body'])
        
        # Save output for review
        with open("test_rfq_neco_output.txt", "w") as f:
            f.write(rfq['body'])
            
    finally:
        agent.close()

if __name__ == "__main__":
    test_targeted_extraction()
