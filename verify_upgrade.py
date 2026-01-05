import os
import sys
import json
import time
from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request

# Target: Use a known solicitation with attachments and complexity
# Example: W912HZ26Q1215 (from previous test file)
TEST_URL = "https://sam.gov/opp/W912HZ26Q1215/view"

def main():
    print("==================================================")
    print("   ELITE PROCUREMENT INTELLIGENCE AGENT - VERIFICATION")
    print("==================================================")

    # 1. Scraping (SamGovAgent)
    print("\n[Phase 1] Scraping SAM.gov...")
    agent = SamGovAgent()
    try:
        # We manually process one page to control the test
        sol_data = agent.process_detail_page(TEST_URL)
        if not sol_data:
            print("FAILED: No data scraped.")
            return
        
        contract_id = sol_data['contract_id']
        print(f"SUCCESS: Scraped Contract {contract_id}")
        
    except Exception as e:
        print(f"CRITICAL ERROR in Phase 1: {e}")
        return
    finally:
        agent.close()

    # 2. Extraction & Analysis (AttachmentReaderAgent)
    print(f"\n[Phase 2] Analyzing Documents for {contract_id}...")
    reader = AttachmentReaderAgent()
    try:
        analysis = reader.create_summary_report(contract_id)
        
        if "error" in analysis:
            print(f"FAILED: Analysis error: {analysis['error']}")
            return
            
        print("SUCCESS: Analysis Complete.")
        
        # Validation Check
        print("\n--- VALIDATION CHECKLIST ---")
        
        # Check 1: Notice ID
        print(f"[*] Notice ID found: {analysis.get('notice_id', 'MISSING')}")
        
        # Check 2: CLINs
        clins = analysis.get('clins', [])
        print(f"[*] CLINs extracted: {len(clins)}")
        if clins:
            print(f"    Sample: {clins[0]}")
            
        # Check 3: Address
        ship_to = analysis.get('delivery_requirements', {}).get('ship_to_address')
        print(f"[*] Ship-To Address: {ship_to}")
        
        # Check 4: Zero Placeholders
        json_str = json.dumps(analysis)
        if "See solicitation" in json_str or "Information not provided" in json_str:
             print("[!] WARNING: Some fields still have placeholders (expected if truly missing).")
        else:
             print("[*] PERFECT: No placeholders detected!")

    except Exception as e:
        print(f"CRITICAL ERROR in Phase 2: {e}")
        return

    # 3. Email Generation (ProposalWriter)
    print("\n[Phase 3] Generating Bid Email...")
    try:
        email = create_bid_request(analysis)
        print("\n" + "-"*40)
        print(f"SUBJECT: {email.get('subject')}")
        print("-" * 40)
        print(email.get('body'))
        print("-" * 40)
        
        if "|" in email.get('body', ''):
             print("[*] SUCCESS: Detected Markdown Table in Email Body (Template Compliant)")
        else:
             print("[!] WARNING: No table found in email body.")
             
    except Exception as e:
        print(f"CRITICAL ERROR in Phase 3: {e}")

if __name__ == "__main__":
    main()
