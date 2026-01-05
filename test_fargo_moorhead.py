
import os
import json
from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request
import config

def test_fargo_moorhead_solicitation():
    notice_id = "W912ES26BA007"
    
    print(f"--- Starting Search for {notice_id} ---")
    sam_agent = SamGovAgent()
    sam_agent.start_browser()
    
    # Search for the solicitation link
    links = sam_agent.search_for_links(search_term=notice_id)
    
    if not links:
        print(f"Could not find solicitation {notice_id} on SAM.gov")
        sam_agent.close()
        return

    sol_url = links[0]
    print(f"Found solicitation link: {sol_url}")
    
    # Scrape detail page
    print("--- Scraping Detail Page ---")
    sol_data = sam_agent.process_detail_page(sol_url)
    
    if not sol_data:
        print("Failed to scrape solicitation data.")
        sam_agent.close()
        return

    # Attachments are handled within process_detail_page (via ensure_solicitation_directory and _deep_download_attachments)
    # The sol_data should contain basic info, the actual documents are in the directory.
    
    # Process with AttachmentReaderAgent
    print("--- Analyzing Content ---")
    reader_agent = AttachmentReaderAgent()
    analysis = reader_agent.create_summary_report(sol_data)
    
    print("--- Analysis Result ---")
    print(json.dumps(analysis, indent=2))
    
    # Generate RFQ
    print("--- Generating RFQ Output ---")
    rfq = create_bid_request(analysis)
    
    print("\n\n--- FINAL RFQ OUTPUT ---\n")
    print(rfq.get('body'))
    
    sam_agent.close()
    
    with open(f"{notice_id}_verify_output.txt", "w") as f:
        f.write(rfq.get('body'))
    print(f"\nOutput saved to {notice_id}_verify_output.txt")

if __name__ == "__main__":
    test_fargo_moorhead_solicitation()
