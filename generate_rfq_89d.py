import sys
import os
import json

# Setup paths
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))

from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager

CONTRACT_ID = "89d87524e3"

def generate_rfq():
    print(f"Initializing AttachmentReaderAgent for {CONTRACT_ID}...")
    agent = AttachmentReaderAgent()
    
    print("Generating RFQ (High Fidelity Mode)...")
    # Using skip_json=True to get direct markdown output from the prompt
    result = agent.create_summary_report(
        contract_id=CONTRACT_ID,
        skip_json=True,
        strict_fidelity=True
    )
    
    if isinstance(result, dict) and "rfq_content" in result:
        content = result["rfq_content"]
        rfq_type = result.get("rfq_type", "UNKNOWN")
        
        output_filename = f"{CONTRACT_ID}_RFQ_{rfq_type}.md"
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"\nSUCCESS: RFQ generated and saved to: {os.path.abspath(output_filename)}")
        print(f"RFQ Type: {rfq_type}")
        print(f"Content Length: {len(content)} bytes")
        
        # Verify content briefly
        lines = content.split('\n')
        print("\n--- Preview (First 20 lines) ---")
        for line in lines[:20]:
            print(line)
        print("--------------------------------")
        
        # Save to DB as well for record
        db_manager = DatabaseManager()
        # We save the markdown content into rfq_outputs table if it exists, or just ensure the analysis record is updated?
        # The schema has rfq_outputs.
        try:
            conn = db_manager._connect_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO rfq_outputs (contract_id, rfq_type, rfq_content, format) VALUES (?, ?, ?, ?)",
                (CONTRACT_ID, rfq_type, content, 'markdown')
            )
            conn.commit()
            print("Saved RFQ to database table 'rfq_outputs'.")
        except Exception as e:
            print(f"Warning: Could not save to rfq_outputs table: {e}")
        finally:
            db_manager._close_db()

    else:
        print("ERROR: Failed to generate RFQ.")
        print(result)

if __name__ == "__main__":
    generate_rfq()
