import os
import sys
import time
import schedule

# Add the parent directory to the Python path to allow imports from other agent directories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import the functions and classes from our other agents
from ai_agents.ContractScoutAgent.contract_scout import find_contract_opportunities
from ai_agents.SolicitationAnalysisAgent.solicitation_analysis import analyze_solicitation
from ai_agents.ProposalWriterAgent.proposal_writer import write_proposal
from ai_agents.OutreachAgent.outreach_agent import send_outreach
from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.VendorScoutAgent.vendor_scout import find_vendors
from ai_agents.NaicsAgent.naics_agent import read_naics_codes_from_xlsx, find_naics_codes
from ai_agents.SummarizationAgent.summarization_agent import summarize_solicitation
from database_manager import create_tables, insert_solicitation
import config

class ProjectManagerAgent:
    def run_workflow(self, naics_codes=None, keywords=None, naics_codes_file=None):
        """
        Runs the full workflow from finding a contract to writing a proposal,
        using the SamGovAgent for vendor searching.

        Args:
            naics_codes (list): A list of NAICS codes to search for.
            keywords (list): A list of keywords to search for.
            naics_codes_file (str): Path to an XLSX file containing NAICS codes.
        """
        create_tables() # Initialize the database
        all_solicitations = []

        search_terms = []
        if naics_codes_file:
            print(f"Reading NAICS codes from XLSX file: {naics_codes_file}")
            naics_codes_from_file = read_naics_codes_from_xlsx(naics_codes_file)
            if naics_codes_from_file:
                search_terms.extend(naics_codes_from_file)
        
        if naics_codes:
            search_terms.extend(naics_codes)
        
        if keywords:
            print(f"Finding NAICS codes for keywords using Gemini API: {keywords}")
            # The find_naics_codes function returns a list of dictionaries, extract just the codes
            found_naics_codes_dicts = find_naics_codes(keywords)
            found_naics_codes = [d["NAICS Code"] for d in found_naics_codes_dicts]
            if found_naics_codes:
                search_terms.extend(found_naics_codes)

        # sam_gov_agent.login() # Login to SAM.gov - Temporarily disabled for direct search
        for search_term in search_terms:
            sam_gov_agent = SamGovAgent() # Create a new agent for each search term
            try:
                print(f"--- Starting Full Workflow for: {search_term} ---")
                solicitations = find_contract_opportunities(search_term, sam_gov_agent) # Pass the agent instance
                all_solicitations.extend(solicitations)
            finally:
                sam_gov_agent.close() # Close the agent after each search term

        if not all_solicitations:
            print("No solicitations found. Exiting workflow.")
            return

        # Remove duplicates
        unique_solicitations = [dict(t) for t in {tuple(d.items()) for d in all_solicitations}]

        # Step 2: Analyze and write a proposal for each opportunity
        for solicitation in unique_solicitations:
            try:
                print(f"\n--- Analyzing and Writing Proposal for: {solicitation['title']} ---")

                # Step 2a: Analyzing the opportunity
                print(f"\nStep 2a: Analyzing the opportunity: {solicitation['url']}")
                analysis_text, details = solicitation_analysis_agent.analyze_solicitation(solicitation)
                print("Solicitation Analysis:")
                print(analysis_text)

                # Save solicitation details to the database
                insert_solicitation(details)

                # Step 2b.1: Summarize the solicitation
                print("\nStep 2b.1: Summarizing the solicitation...")
                solicitation_summary = summarize_solicitation(details)
                print("Solicitation Summary:")
                print(solicitation_summary)

                # Step 4: Write a proposal (using the analysis)
                print("\nStep 4: Writing proposal...")
                proposal_text = proposal_writer_agent.write_proposal(analysis_text, details)
                print("Proposal Draft:")
                print(proposal_text)

                # Step 5: Find vendors (using the analysis details)
                print("\nStep 5: Finding vendors...")
                vendors = vendor_scout_agent.find_vendors(analysis_details)
                print("Potential Vendors:", vendors)

                # Step 6: Send outreach emails
                print("\nStep 6: Sending outreach emails...")
                outreach_agent.send_outreach(
                    solicitation_title=details.get('solicitation_title', 'N/A'),
                    solicitation_url=details.get('url', 'N/A'),
                    solicitation_summary=solicitation_summary, # Pass the summary
                    proposal_text=proposal_text,
                    vendors=vendors,
                    contact_info=details.get('primary_poc', {}),
                    attachments=details.get('attachments', [])
                )

                # Step 2e: Present the final proposal
                print("\n--- Proposal Generation and Outreach Complete ---")
                print("\nFinal Generated Proposal:")
                print(proposal)

            except Exception as e:
                print(f"An error occurred while processing solicitation: {solicitation['title']}")
                print(e)

        print("\n--- Full Workflow Complete ---")

if __name__ == "__main__":
    manager = ProjectManagerAgent()
    
    # Set the specific NAICS code to search for
    specific_naics_code = ["products"]
    keywords_for_naics_generation = [] # Empty the keywords to avoid unnecessary Gemini API calls
    naics_codes_xlsx_file = None # Explicitly ignore the XLSX file

    manager.run_workflow(naics_codes=specific_naics_code, keywords=keywords_for_naics_generation, naics_codes_file=naics_codes_xlsx_file)

    # Schedule the job to run every hour
    schedule.every().hour.do(manager.run_workflow, naics_codes=None, keywords=keywords_for_naics_generation, naics_codes_file=naics_codes_xlsx_file)
    
    print("Scheduler started. The workflow will run again in one hour.")
    # Run the scheduler indefinitely
    while True:
        schedule.run_pending()
        time.sleep(1)