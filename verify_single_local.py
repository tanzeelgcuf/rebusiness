import sys
import os
import json
import time
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request
from database_manager import DatabaseManager

CONTRACT_ID = "9e8fbcc66b" 

def seed_database(contract_id):
    db = DatabaseManager()
    base_dir = f"data/solicitations/{contract_id}"
    
    # Read metadata
    try:
        with open(f"{base_dir}/metadata.json", "r") as f:
            meta = json.load(f)
    except:
        meta = {"title": "Test Solicitation", "url": "http://test.com", "contract_id": contract_id}
        
    print(f"  [Seeding] Inserting solicitation {contract_id} into DB...")
    db.add_solicitation(
        contract_id=contract_id,
        url=meta.get('url'),
        title=meta.get('title'),
        description="Test Description",
        location="USA",
        product_requirements="N/A",
        analysis_summary=None,
        data="{}"
    )
    
    # Add attachments from disk
    att_dir = f"{base_dir}/attachments"
    if os.path.exists(att_dir):
        for fname in os.listdir(att_dir):
            if fname.startswith('.'): continue
            fpath = os.path.abspath(os.path.join(att_dir, fname))
            print(f"  [Seeding] Adding attachment: {fname}")
            db.add_attachment(contract_id, fname, fpath, meta.get('url'), time.time())

def main():
    print(f"--- Verifying Template on Local Contract: {CONTRACT_ID} ---")
    
    seed_database(CONTRACT_ID)
    
    print("  [DEBUG] Testing LLM Connection directly...")
    reader = AttachmentReaderAgent()
    try:
        # Test direct analysis
        test_parts = ["This is a test solicitation for 50 laptops. Notice ID: TEST-123. Due: 2026-01-01."]
        result = reader._analyze_content_with_llm(test_parts)
        print(f"  [DEBUG] LLM Result: {str(result)[:100]}...")
        if not result or "error" in result:
             print("  [DEBUG] LLM returned empty or error.")
    except Exception as e:
        print(f"  [DEBUG] LLM Failed: {e}")
        return

    # 2. Extract
    print("  [1] Analyzing Attachments...")
    # reader = AttachmentReaderAgent() # Already init
    analysis = reader.create_summary_report(CONTRACT_ID)
    
    if not analysis or "error" in analysis:
        print(f"Analysis failed: {analysis}")
        # Proceed with Mock Data if analysis fails, so we can verify Template Generation
        print("  [!] Falling back to MOCK DATA to verify Template Generation...")
        analysis = {
            "solicitation_type": "PRODUCT",
            "title": "MOCK: Supply of tactical gear",
            "soliciting_entity": {"name": "DLA Troop Support"},
            "dates": {"due": "2026-02-15"},
            "clins": [
                {"clin": "0001", "description": "Tactical Vest, Level IV", "qty": 500, "unit": "EA"},
                {"clin": "0002", "description": "Helmet, Ballistic", "qty": 500, "unit": "EA"}
            ],
            "delivery_requirements": {
                "ship_to_address": {
                     "organization": "DLA Distribution",
                     "street": "123 Supply Rd",
                     "city": "New Cumberland",
                     "state": "PA",
                     "zip": "17070"
                },
                "fob_point": "Destination"
            },
            "compliance": {
                "set_aside": "Small Business",
                "wage_determination": "N/A"
            },
            "contract_details": {"naics_code": "315220"}
        }

    # 3. Write Proposal
    print("  [2] Generating Email Draft...")
    email_draft = create_bid_request(analysis)
    
    print("\n" + "="*60)
    print("GENERATED EMAIL OUTPUT")
    print("="*60)
    print(f"SUBJECT: {email_draft.get('subject')}")
    print("-" * 30)
    print(email_draft.get('body'))
    print("="*60)
    
    # Verification Logic
    body = email_draft.get('body', '')
    sol_type = analysis.get('solicitation_type', 'PRODUCT').upper()
    is_product = "PRODUCT" in sol_type or "SUPPLY" in sol_type
    
    print("\n--- TEMPLATE COMPLIANCE CHECK ---")
    print(f"Detected Type: {sol_type}")
    
    if is_product:
        print("Target Template: Claude Vendor List.odt (Product)")
        checks = [
            ("Request for Quote (RFQ)", "RFQ Section"),
            ("| CLIN |", "CLIN Table"),
            ("Shipping / Delivery", "Shipping Section"),
            ("Compliance & Stats", "Compliance Section")
        ]
    else:
        print("Target Template: Claude Services List.odt (Service)")
        checks = [
            ("Scope of Work", "Scope Section"),
            ("Performance Locations", "Locations Section"),
            ("Labor & Compliance", "Labor Section")
        ]

    score = 0
    for text, name in checks:
        if text in body:
            print(f"  [PASS] {name} found.")
            score += 1
        else:
            print(f"  [FAIL] {name} NOT found.")
            
    if score == len(checks):
        print("\n>>> VERDICT: 100% TEMPLATE MATCH <<<")
    else:
        print(f"\n>>> VERDICT: {score}/{len(checks)} MATCH - REVIEW REQUIRED <<<")

if __name__ == "__main__":
    main()
