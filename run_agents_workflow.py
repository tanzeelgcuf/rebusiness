import os
import sys
import json
import time
# Add parent directory to path to import ai_agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from DescriptionDownloaderAgent.description_downloader_agent import DescriptionDownloaderAgent
from AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ProposalWriterAgent.proposal_writer import write_proposal
from MappingAgent.mapping_agent import MappingAgent
from OutreachAgent.outreach_agent import send_email
from database_manager import DatabaseManager

def run_workflow():
    # This is a test URL from a previous run. You can replace it with a current, valid SAM.gov URL.
    solicitation_url = "https://sam.gov/workspace/contract/opp/82952ba3b2174a428722110fc27d97ac/view"
    
    # Initialize DatabaseManager to ensure tables are created
    db_manager = DatabaseManager()

    # --- Step 1: Run DescriptionDownloaderAgent ---
    print("\n--- Running DescriptionDownloaderAgent ---")
    description_downloader_agent = None
    solicitation_data = None
    # Extract contract ID from URL to check if data already exists
    contract_id_from_url = solicitation_url.split('/')[-2]

    try:
        # Set headless=True for silent operation, False to see browser
        description_downloader_agent = DescriptionDownloaderAgent(headless=False, download_dir="downloads")
        solicitation_data, downloaded_files = description_downloader_agent.scrape_and_download(solicitation_url)

        if solicitation_data:
            print(f"\nDescriptionDownloaderAgent completed for contract ID: {solicitation_data['contract_id']}")
            print(f"Downloaded {len(downloaded_files)} files.")
        else:
            print("DescriptionDownloaderAgent failed to scrape or download.")
            # Fallback to check if the data is already in the database from a previous run
            solicitation_row = db_manager.get_solicitation_by_contract_id(contract_id_from_url)
            if not solicitation_row:
                print(f"No data found in DB for {contract_id_from_url}. Exiting.")
                return
            else:
                solicitation_data = dict(solicitation_row)
                print(f"Found existing data in DB for {solicitation_data['contract_id']}. Proceeding with existing data.")

    finally:
        if description_downloader_agent:
            description_downloader_agent.close()

    contract_id = solicitation_data['contract_id'] if solicitation_data else contract_id_from_url
    if not contract_id:
        print("Could not determine contract_id. Exiting.")
        return

    # --- Step 2: Run AttachmentReaderAgent ---
    print(f"\n--- Running AttachmentReaderAgent for contract ID: {contract_id} ---")
    attachment_reader_agent = AttachmentReaderAgent()
    structured_analysis = attachment_reader_agent.create_summary_report(contract_id)
    
    # Re-fetch solicitation data from DB to ensure it's up-to-date before updating
    solicitation_for_update_row = db_manager.get_solicitation_by_contract_id(contract_id)
    if solicitation_for_update_row:
        solicitation_for_update = dict(solicitation_for_update_row)
        db_manager.add_solicitation( # Using add_solicitation to update
            contract_id=contract_id,
            url=solicitation_for_update.get('url'),
            title=solicitation_for_update.get('title', 'N/A'),
            description=solicitation_for_update.get('description'),
            location=solicitation_for_update.get('location'),
            product_requirements=solicitation_for_update.get('product_requirements'),
            analysis_summary=json.dumps(structured_analysis), # Store as JSON string
            data=solicitation_for_update.get('data')
        )
        print(f"AttachmentReaderAgent completed and saved analysis for {contract_id}.")
    else:
        print(f"Could not find solicitation {contract_id} in DB to update with analysis summary.")
        return

    # --- Step 3: Run ProposalWriterAgent ---
    print(f"\n--- Running ProposalWriterAgent for contract ID: {contract_id} ---")
    solicitation_row = db_manager.get_solicitation_by_contract_id(contract_id)
    if solicitation_row:
        solicitation = dict(solicitation_row)
        solicitation_analysis = solicitation['analysis_summary'] or solicitation['description']
        if solicitation['analysis_summary']:
            print("Using analysis_summary to generate proposal.")
        else:
            print("analysis_summary not found, falling back to description to generate proposal.")

        proposal_text = write_proposal(solicitation_analysis, solicitation)
        db_manager.add_proposal(contract_id, proposal_text)
        print(f"--- Generated Proposal for {contract_id} ---")
        print((proposal_text[:1000] + "...") if len(proposal_text) > 1000 else proposal_text) # Print first 1000 chars
    else:
        print(f"Could not find solicitation {contract_id} in the database to write proposal.")
        solicitation = None # Ensure solicitation is None if not found

    # --- Step 4: Conditional Mapping and Outreach ---
    print(f"\n--- Conditional Mapping and Outreach for contract ID: {contract_id} ---")
    if solicitation:
        location = solicitation.get('location')
        
        # Add a fallback for location if it's None in the database
        if not location:
            # Based on the summary, the attachments mention "Washington County of Pierce" and "King County"
            # So, "Seattle, WA" is a reasonable default for testing
            location = "Seattle, WA"
            print(f"Location was None, using fallback location: {location} for {contract_id}.")

        # Construct product_requirements from analysis_summary or fallback to original
        product_requirements = "" # Initialize with empty string
        if solicitation.get('analysis_summary'):
            try:
                analysis = json.loads(solicitation['analysis_summary'])
                combined_summary_parts = []
                if analysis.get('description_summary'):
                    combined_summary_parts.append(analysis['description_summary'])
                if analysis.get('attachment_summaries'):
                    for att_summary in analysis['attachment_summaries']:
                        if att_summary.get('summary'):
                            combined_summary_parts.append(att_summary['summary'])
                
                if combined_summary_parts:
                    product_requirements = "\n".join(combined_summary_parts)
                    print(f"Constructed product requirements from analysis_summary for {contract_id}.")
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Could not parse analysis_summary for {contract_id} ({e}), falling back to original product_requirements.")
        
        # If product_requirements is still empty after trying analysis_summary, fall back to original
        if not product_requirements:
            product_requirements = solicitation.get('product_requirements')
            if product_requirements:
                print(f"No product requirements found in analysis_summary, using original product_requirements for {contract_id}.")
            else:
                print(f"No product requirements found for {contract_id} in analysis_summary or original data.")

        # --- Run MappingAgent if location is available ---
        if location and product_requirements:
            # Truncate product_requirements for the Google Maps query to avoid exceeding character limits
            mapping_query_requirements = (product_requirements[:250] + '...') if len(product_requirements) > 250 else product_requirements

            mapping_agent = MappingAgent()
            mapping_agent.find_vendors(contract_id, location, mapping_query_requirements)
            
            # --- Run OutreachAgent to email found vendors ---
            print(f"\n--- Running OutreachAgent for vendors of contract ID: {contract_id} ---")
            vendors = db_manager.get_vendors_for_solicitation(contract_id)
            if vendors:
                smtp_config = {
                    "smtp_server": "smtp.example.com", "smtp_port": 587,
                    "smtp_username": "your_username", "smtp_password": "your_password",
                    "sender_email": "your_email@example.com"
                }
                for vendor_row in vendors:
                    vendor = dict(vendor_row)
                    if vendor.get('email'):
                        email_subject = f"Inquiry regarding: {solicitation['title']}"
                        email_body = f"""Dear {vendor['name']},

We are preparing a proposal for the solicitation '{solicitation['title']}' and are looking for potential suppliers for the required services/products.

Summary of requirements:
{product_requirements}

Would your company be interested in providing a quote for these requirements?

Thank you,
The Rebusiness Automation Project Team
"""
                        send_email(vendor['email'], email_subject, email_body, smtp_config)
                    else:
                        print(f"Skipping email for vendor {vendor['name']} as no email is available.")
            else:
                print("No vendors found to email.")

        # --- Fallback to emailing POC if location logic fails ---
        else:
            primary_poc_email = solicitation.get('primary_poc', {}).get('email')
            if primary_poc_email:
                print(f"Could not find vendors via mapping. Sending bid request to primary POC: {primary_poc_email}")
                smtp_config = {
                    "smtp_server": "smtp.example.com", "smtp_port": 587,
                    "smtp_username": "your_username", "smtp_password": "your_password",
                    "sender_email": "your_email@example.com"
                }
                email_subject = f"Inquiry regarding: {solicitation['title']}"
                email_body = f"""Dear {solicitation.get('primary_poc', {}).get('name', 'Point of Contact')},

We are interested in the solicitation '{solicitation['title']}'. We are looking for potential suppliers for the required services/products.

Summary of requirements:
{product_requirements}

Could you please provide any information on potential suppliers or point us in the right direction?

Thank you,
The Rebusiness Automation Project Team
"""
                send_email(primary_poc_email, email_subject, email_body, smtp_config)

            # --- Skip if no location and no POC email ---
            else:
                print(f"Skipping outreach for solicitation {contract_id} as there is no location and no primary contact email.")

    else:
        print(f"Could not find solicitation {contract_id} in the database for mapping and outreach.")


if __name__ == "__main__":
    run_workflow()