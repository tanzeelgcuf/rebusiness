
import os
import json
import sys
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request

def test_extraction():
    print("--- Starting Extraction Verification ---")
    
    contract_id = "218fe9a046"
    reader = AttachmentReaderAgent()
    
    print(f"Step 1: Analyzing content for Contract ID: {contract_id}...")
    try:
        analysis_result = reader.create_summary_report(contract_id)
        
        # Save analysis
        with open("test_extraction_output_manual.json", "w") as f:
            json.dump(analysis_result, f, indent=2)
        print("Analysis saved to test_extraction_output_manual.json")
        
        # Step 2: Generate RFQ
        print("Step 2: Generating RFQ...")
        
        # Mock solicitation type if not in analysis (though it should be)
        solicitation_type = analysis_result.get("solicitation_type", "PRODUCT")
        
        rfq = create_bid_request(analysis_result, "Test Vendor")
        
        with open("test_rfq_output_manual.txt", "w") as f:
            f.write(f"Subject: {rfq['subject']}\n\n{rfq['body']}")
        print("RFQ saved to test_rfq_output_manual.txt")
        
    except Exception as e:
        print(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_extraction()
