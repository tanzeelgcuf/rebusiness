
"""
Verification script for the new SAMGovExtractor.
Runs the strict extraction capability against the known completel solicitation (197aaa46...).
"""

import sqlite3
import json
import logging
from ai_agents.SAMGovExtractor.sam_gov_extractor import SAMGovExtractor

logging.getLogger().setLevel(logging.INFO)

DB_PATH = "rebusiness_automation.db"
TARGET_CONTRACT_ID = "197aaa46ad6c461db627c6934ba7fea4"

def verify_extraction():
    print(f"🔬 Verifying SAMGovExtractor on contract: {TARGET_CONTRACT_ID}")
    
    # 1. Fetch Solicitation Data from DB
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get Solicitation Content
    cursor.execute("SELECT url, data, analysis_summary FROM solicitations WHERE contract_id = ?", (TARGET_CONTRACT_ID,))
    sol_row = cursor.fetchone()
    
    if not sol_row:
        print("❌ Contract not found in DB.")
        return

    # Mocking HTML content (since we don't store raw HTML in DB, we use the 'data' or 'analysis_summary' or similar text source)
    # Ideally should re-scrape, but for now we'll check if we have enough text in 'data' or construct a mock text
    # Actually, let's use the 'analysis_summary' + 'data' as a proxy for the Main Text for this test
    sol_data = json.loads(sol_row['data'])
    main_text = f"Title: {sol_row['url']}\n\nExisting Data Source: {sol_row['data']}\n\nSummary: {sol_row['analysis_summary']}"
    
    # Get Attachments
    # Get Attachments
    cursor.execute("SELECT file_name, file_path FROM attachments WHERE contract_id = ?", (TARGET_CONTRACT_ID,))
    att_rows = cursor.fetchall()
    
    attachments = []
    print(f"📎 Found {len(att_rows)} attachments.")
    
    # We need to read the actual file content from disk to simulate the pipeline
    # We will use AttachmentReaderAgent logic (or a simple PDF reader since we know they are PDFs)
    # For verification speed, let's just use PyPDF2 directly here or try to read text if it's text.
    import PyPDF2
    
    for row in att_rows:
        f_path = row['file_path']
        f_name = row['file_name']
        
        # Verify file exists
        import os
        if not os.path.exists(f_path):
            print(f"⚠️ File missing on disk: {f_path}")
            continue
            
        content = ""
        try:
            if f_path.lower().endswith('.pdf'):
                with open(f_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        content += page.extract_text() + "\n"
            else:
                # Fallback for text
                with open(f_path, 'r', errors='ignore') as f:
                    content = f.read()
            
            if content.strip():
                 attachments.append({
                    'filename': f_name,
                    'content': content
                })
        except Exception as e:
            print(f"⚠️ Error reading {f_name}: {e}")
    
    conn.close()
    
    # 2. Run Extractor
    extractor = SAMGovExtractor()
    result = extractor.extract_solicitation(main_text, attachments)
    
    # 3. Analyze Results
    print("\n📝 FULL EXTRACTED JSON:")
    print(json.dumps(result, indent=2))
    
    print("\n🔍 REQUIRED FIELDS CHECK:")
    fields_to_check = {
        'agency_name': result.get('agency_name'),
        'agency_address': result.get('agency_address'),
        'quotes_due_date': result.get('quotes_due_date'),
        'contract_type': result.get('contract_type')
    }
    
    for k, v in fields_to_check.items():
        print(f"  - {k}: {v}")
        
    print("\n📦 DELIVERY REQUIREMENTS CHECK:")
    dr = result.get('delivery_requirements', {})
    print(f"  - Address: {dr.get('address') or dr.get('primary_destination_address')}")
    print(f"  - Schedule: {dr.get('schedule_days') or dr.get('schedule_details')}")
    
    print(f"\n✅ VALIDATION STATUS: {result.get('extraction_status')}")
    if result.get('validation_errors'):
        print("❌ Errors:", result.get('validation_errors'))
    else:
        print("🎉 No validation errors found!")

if __name__ == "__main__":
    verify_extraction()
