import sys
import os
import json
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request

CONTRACT_ID = "9e8fbcc66b" 

def main():
    print(f"--- Verifying Template on Local Contract: {CONTRACT_ID} ---")
    
    # 2. Extract
    print("  [1] Analyzing Attachments...")
    reader = AttachmentReaderAgent()
    analysis = reader.create_summary_report(CONTRACT_ID)
    
    if "error" in analysis:
        print(f"Analysis failed: {analysis['error']}")
        return

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
