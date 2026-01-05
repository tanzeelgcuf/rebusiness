import sys
import os
import json
import time

# Ensure we can import modules
sys.path.append(os.getcwd())

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request

def main():
    keyword = "equipment"
    print(f"--- Running Template Verification for keyword: '{keyword}' ---")
    
    # 1. Search & Scrape
    agent = SamGovAgent()
    solicitations = []
    try:
        print("  [1] Searching SAM.gov...")
        # Search for fresh solicitations
        # We manually call search_and_scrape to control the output
        solicitations = agent.search_and_scrape(keyword, max_pages=1)
    except Exception as e:
        print(f"Search failed: {e}")
    finally:
        agent.close()

    if not solicitations:
        print("No solicitations found. Try a different keyword.")
        return

    # Pick the first one
    target_sol = solicitations[0]
    contract_id = target_sol['contract_id']
    print(f"  [2] Targeted Solicitation: {target_sol['title']} (ID: {contract_id})")

    # 2. Extract
    print("  [3] Analyzing Attachments...")
    reader = AttachmentReaderAgent()
    analysis = reader.create_summary_report(contract_id)
    
    if "error" in analysis:
        print(f"Analysis failed: {analysis['error']}")
        return

    # 3. Write Proposal
    print("  [4] Generating Email Draft...")
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
    # Check if type is effectively product or service
    sol_type = analysis.get('solicitation_type', 'PRODUCT').upper()
    is_product = "PRODUCT" in sol_type or "SUPPLY" in sol_type
    
    print("\n--- TEMPLATE COMPLIANCE CHECK ---")
    print(f"Detected Type: {sol_type}")
    
    if is_product:
        print("Target Template: Claude Vendor List.odt (Product)")
        # Key phrases from the Product template structure I implemented
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
