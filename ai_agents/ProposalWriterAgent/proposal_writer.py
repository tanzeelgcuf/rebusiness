import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import config
from database_manager import DatabaseManager
import google.generativeai as genai
import json
import re
from openai import OpenAI # Import OpenAI client

# Configure the generative AI model
if config.LLM_PROVIDER == "gemini":
    genai.configure(api_key=config.GEMINI_API_KEY)

def create_bid_request(analysis_summary, vendor_name="Valued Supplier"):
    """
    Creates a professional and personalized bid request email draft.

    Args:
        analysis_summary (dict): A dictionary containing the structured analysis of a solicitation.
        vendor_name (str): The name of the vendor to personalize the email.

    Returns:
        dict: A dictionary containing the email subject and body.
    """
    analysis_summary = analysis_summary if isinstance(analysis_summary, dict) else {}
    solicitation_type = analysis_summary.get('solicitation_type', 'PRODUCT').upper()
    
    # Common Data
    title = analysis_summary.get('title', 'N/A')
    agency = analysis_summary.get('soliciting_entity', {}).get('name', 'Government Agency')
    closing_date = analysis_summary.get('dates', {}).get('due', 'See Solicitation')
    
    # 1. Product Layout (Claude Vendor List.odt)
    if "PRODUCT" in solicitation_type:
        clins = analysis_summary.get('clins', [])
        clin_table = "| CLIN | Description | Qty | Unit |\n|---|---|---|---|\n"
        for c in clins:
            clin_table += f"| {c.get('clin')} | {c.get('description')} | {c.get('qty')} | {c.get('unit')} |\n"
            
        ship_to = analysis_summary.get('delivery_requirements', {}).get('ship_to_address', 'See Solicitation')
        if isinstance(ship_to, dict):
             ship_str = f"{ship_to.get('organization','')}\n{ship_to.get('street','')}\n{ship_to.get('city','')}, {ship_to.get('state','')} {ship_to.get('zip','')}"
        else: ship_str = str(ship_to)

        prompt_context = f"""
        TEMPLATE: PRODUCT (Vendor List)
        STRUCTURAL REQUIREMENTS:
        - Greeting: "Hi [Vendor Name]," (Casual but professional)
        - Opening: "We are bidding on [Title] ({agency}). Closing Date: {closing_date}."
        - Section 1: **Request for Quote (RFQ)** (Bold Header)
        - Table: Insert the CLIN table below exactly.
        {clin_table}
        - Section 2: **Shipping / Delivery**
        - Address: {ship_str}
        - Terms: FOB Destination? {analysis_summary.get('delivery_requirements', {}).get('fob_point', 'Unknown')}
        - Section 3: **Compliance & Stats**
        - Set-Aside: {analysis_summary.get('compliance', {}).get('set_aside', 'None')}
        - NAICS: {analysis_summary.get('contract_details', {}).get('naics_code')}
        - Closing: "Please provide pricing and lead times by [Internal Date]."
        - Signature: {point_of_contact}, Campsable.com
        """

    # 2. Service Layout (Claude Services List.odt)
    else:
        scope = analysis_summary.get('service_scope', {}).get('pws_summary', 'See PWS')
        locs = analysis_summary.get('service_scope', {}).get('locations', [])
        loc_str = "\n".join([f"- {l}" for l in locs])
        
        wd = analysis_summary.get('compliance', {}).get('wage_determination', 'N/A')
        
        prompt_context = f"""
        TEMPLATE: SERVICE (Services List)
        STRUCTURAL REQUIREMENTS:
        - Greeting: "Hello [Vendor Name],"
        - Opening: "We are preparing a proposal for [Title] ({agency}). Due: {closing_date}."
        - Section 1: **Scope of Work** (Bold Header)
        - Summary: {scope}
        - Section 2: **Performance Locations**
        {loc_str}
        - Section 3: **Labor & Compliance**
        - Wage Determination: {wd}
        - Insurance: Customary limits apply.
        - Section 4: **Submission Requirements**
        - Ask for: Capability Statement, Past Performance (3 refs), Key Personnel Resumes.
        - Closing: "Please confirm interest/availability by [Internal Date]."
        - Signature: {point_of_contact}, Campsable.com
        """

    prompt = f"""
    You are a Procurement Agent for Campsable.com. Write a vendor email based **STRICTLY** on the layout below.
    
    CONTEXT:
    {prompt_context}
    
    OUTPUT JSON: {{ "subject": "...", "body": "..." }}
    """

    try:
        if config.LLM_PROVIDER == "openai":
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=1000 # Adjusted max tokens for email generation
            )
            return json.loads(response.choices[0].message.content)
        else: # Default to gemini
            model = genai.GenerativeModel('gemini-2.5-pro', generation_config={"response_mime_type": "application/json"})
            response = model.generate_content(prompt)
            return json.loads(response.text)
    except Exception as e:
        print(f"Error creating bid request: {e}")
        return {
            "subject": f"Inquiry for Quote: {title}",
            "body": f"Dear {vendor_name} Team,\n\nError generating bid request. Please review manually.\n\nBest regards,\n{point_of_contact}\nCampsable.com"
        }

if __name__ == "__main__":
    db_manager = DatabaseManager()
    
    conn = db_manager._connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT contract_id, analysis_summary FROM solicitations WHERE analysis_summary IS NOT NULL")
    all_solicitations = cursor.fetchall()
    db_manager._close_db()

    if not all_solicitations:
        print("No solicitations with analysis summaries found in the database.")
    else:
        for solicitation_row in all_solicitations:
            solicitation = dict(solicitation_row)
            contract_id = solicitation['contract_id']
            
            try:
                analysis_summary = json.loads(solicitation['analysis_summary'])
                print(f"--- Creating bid request for: {analysis_summary.get('title', contract_id)} ---")
                
                bid_request_email = create_bid_request(analysis_summary)
                
                # In a real scenario, this email would be sent or saved as a draft.
                # For now, we'll just print it.
                print(f"Subject: {bid_request_email['subject']}")
                print("\n--- Email Body ---")
                print(bid_request_email['body'])
                
                # Optionally, save this generated text back to the proposals table
                # For consistency, we can save the body of the email as the 'proposal_text'
                db_manager.add_proposal(contract_id, json.dumps(bid_request_email))

            except (json.JSONDecodeError, TypeError) as e:
                print(f"Could not process solicitation {contract_id}. Error decoding analysis summary: {e}")

            print("\n" + "="*80 + "\n")
