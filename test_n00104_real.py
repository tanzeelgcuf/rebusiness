
import sqlite3
import json
import sys
import os

# Add paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents/ProposalWriterAgent')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents/AttachmentReaderAgent')))
from proposal_writer import create_bid_request
# Assuming extract_solicitation_data is available or similar
# actually we used AttachmentReaderAgent in test_fargo_moorhead_local.py

def process_real_data():
    db_path = 'rebusiness_automation.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    nid = "N0010425QNF13"
    print(f"Querying for {nid}...")
    cursor.execute("SELECT * FROM solicitations WHERE contract_id = ?", (nid,))
    row = cursor.fetchone()
    
    if not row:
        print("Not found.")
        return

    data_json = row['data']
    analysis_json = row['analysis_summary']
    
    summary_data = None
    if analysis_json:
        try:
            summary_data = json.loads(analysis_json)
            # Ensure notice_id is formatted with dashes if preferred, or keep as is
            # User output example showed "N00104-25-Q-NF13"
            summary_data['notice_id'] = "N00104-25-Q-NF13" 
        except:
            print("Failed to parse analysis_summary")

    if not summary_data and data_json:
         print("No analysis summary, parsing raw data not implemented in this quick script (requires full agent).")
         # If needed, we would verify files and run agent here.
         return

    if summary_data:
        print("Existing analysis found. Generating RFQ...")
        # Fix project title to be upper case if desired
        if 'project_title' in summary_data:
             summary_data['project_title'] = summary_data['project_title'].upper()
             
        # Add explicit Vendor Tips bypass if needed or rely on dynamic
        # Force it to be treated as SERVICE if unspecified
        if 'solicitation_type' not in summary_data:
            summary_data['solicitation_type'] = 'SERVICE'

        output = create_bid_request(summary_data)
        
        filename = "N00104_verify_output_real.txt"
        with open(filename, 'w') as f:
            f.write(output['body'])
            
        print(f"Generated {filename}")
        print("Preview:")
        print(output['body'][:500])
    else:
        print("No analysis data available to process.")

    conn.close()

if __name__ == "__main__":
    process_real_data()
