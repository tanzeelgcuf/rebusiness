
import os
import json
import sqlite3
import time
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request
from database_manager import DatabaseManager
import config

def test_fargo_moorhead_local():
    notice_id = "W912ES26BA007"
    sol_dir = "data/solicitations/2615d6536b"
    
    # 1. Register solicitation in DB if not present
    conn = sqlite3.connect("rebusiness_automation.db")
    cursor = conn.cursor()
    
    # Check if exists
    cursor.execute("SELECT contract_id FROM solicitations WHERE contract_id = ?", (notice_id,))
    if not cursor.fetchone():
        print(f"Adding {notice_id} to database...")
        cursor.execute("""
            INSERT INTO solicitations (contract_id, url, title, description, location)
            VALUES (?, ?, ?, ?, ?)
        """, (
            notice_id, 
            f"https://sam.gov/opp/{notice_id}/view", 
            "Fargo-Moorhead Forest Mitigation Planting",
            "Establish, monitor, and maintain native forest habitat as environmental mitigation for the Fargo-Moorhead Metropolitan Flood Risk Management Project.",
            "Cass County, ND and Clay County, MN"
        ))
        conn.commit()
    
    # 2. Register attachments in DB
    att_dir = os.path.join(sol_dir, "attachments")
    if os.path.exists(att_dir):
        for f in os.listdir(att_dir):
            if not (f.lower().endswith(".pdf") or f.lower().endswith(".docx")):
                continue
                
            file_path = os.path.join(att_dir, f)
            cursor.execute("SELECT id FROM attachments WHERE contract_id = ? AND file_name = ?", (notice_id, f))
            if not cursor.fetchone():
                print(f"Registering attachment: {f}")
                cursor.execute("""
                    INSERT INTO attachments (contract_id, file_name, file_path, download_date)
                    VALUES (?, ?, ?, ?)
                """, (notice_id, f, file_path, time.time()))
        conn.commit()
    
    conn.close()

    # 3. Process with AttachmentReaderAgent
    print("--- Analyzing Local Content (v8) ---")
    reader_agent = AttachmentReaderAgent()
    analysis = reader_agent.create_summary_report(notice_id)
    
    if "error" in analysis:
        print(f"Error in analysis: {analysis['error']}")
        return

    # Save analysis for debugging
    with open(f"{notice_id}_analysis_v10.json", "w") as f:
        json.dump(analysis, f, indent=2)
    
    print("--- Generating RFQ Output (v8) ---")
    rfq = create_bid_request(analysis)
    
    output_body = rfq.get('body')
    
    with open(f"{notice_id}_verify_output_v10.txt", "w") as f:
        f.write(output_body)
    print(f"\nOutput saved to {notice_id}_verify_output_v10.txt")
    print("\n--- PREVIEW OF OUTPUT ---")
    print(output_body[:1000] + "...")

if __name__ == "__main__":
    test_fargo_moorhead_local()
