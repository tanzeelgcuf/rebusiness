#!/usr/bin/env python3
import sys
import os
import sqlite3
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent

DB_PATH = "rebusiness_automation.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check for specific IDs in command line args
    if len(sys.argv) > 1:
        contract_ids = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    else:
        # Find unique solicitations for pending requests
        cursor.execute("""
            SELECT DISTINCT p.contract_id 
            FROM manufacturer_requests mr 
            JOIN products p ON mr.product_id = p.id 
            WHERE mr.status = 'pending'
        """)
        contract_ids = [row[0] for row in cursor.fetchall()]
    
    print(f"Found {len(contract_ids)} solicitations to re-extract.")
    
    agent = AttachmentReaderAgent()
    
    for cid in contract_ids:
        print(f"\nProcessing {cid}...")
        # Force re-extraction by deleting old analysis
        cursor.execute("DELETE FROM solicitation_analysis WHERE contract_id = ?", (cid,))
        conn.commit()
        
        try:
            analysis = agent.create_summary_report(cid)
            if analysis and "error" not in analysis:
                analysis_json = json.dumps(analysis)
                cursor.execute("UPDATE solicitations SET analysis_summary = ? WHERE contract_id = ?", (analysis_json, cid))
                conn.commit()
                print(f"✅ Successfully re-extracted and saved {cid}")
            else:
                print(f"⚠️  Extraction returned error for {cid}")
        except Exception as e:
            print(f"❌ Failed to extract {cid}: {e}")
            
    conn.close()
    print("\nBatch re-extraction complete.")

if __name__ == "__main__":
    main()
