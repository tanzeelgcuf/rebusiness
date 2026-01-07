
import os
import sys
import json
import sqlite3

# Agent Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents/AttachmentReaderAgent')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents/ProposalWriterAgent')))
from attachment_reader_agent import AttachmentReaderAgent
from proposal_writer import create_bid_request

def reprocess_n00104():
    contract_id = "N0010425QNF13"
    
    # Process with AttachmentReaderAgent
    print("Calling AttachmentReaderAgent...")
    reader = AttachmentReaderAgent()
    
    print(f"Processing contract: {contract_id}")
    analysis = reader.create_summary_report(contract_id)
    
    # Save analysis for inspection
    with open('N00104_reanalysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print("Generating RFQ...")
    
    # Force Service Type if not detected
    if 'solicitation_type' not in analysis:
        analysis['solicitation_type'] = 'SERVICE'
        
    analysis['notice_id'] = "N00104-25-Q-NF13" # Format nicely
    
    output = create_bid_request(analysis)
    
    out_file = "N00104_verify_output_reprocess.txt"
    with open(out_file, 'w') as f:
        f.write(output['body'])
        
    print(f"Done. Saved to {out_file}")

if __name__ == "__main__":
    reprocess_n00104()
