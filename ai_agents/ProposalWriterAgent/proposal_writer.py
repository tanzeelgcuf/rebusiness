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
    # Extracting structured data
    product_details = analysis_summary.get('product_details', [])
    delivery_location_obj = analysis_summary.get('delivery_location', {})
    summary = analysis_summary.get('summary', 'No summary available.')
    title = analysis_summary.get('title', 'N/A')
    agency = analysis_summary.get('agency', 'a government agency')
    point_of_contact = config.COMPANY_INFO.get("Point of Contact", "John Campbell") # Get sender name

    # Format product details for the prompt
    formatted_product_details = []
    if product_details:
        for i, p_item in enumerate(product_details):
            details = [f"Item {i+1}: {p_item.get('name', 'N/A')}"]
            if p_item.get('line_item_number'):
                details.append(f"  - Line Item: {p_item.get('line_item_number')}")
            if p_item.get('quantity') and p_item.get('unit'):
                details.append(f"  - Quantity: {p_item.get('quantity')} {p_item.get('unit')}")
            if p_item.get('part_number'):
                details.append(f"  - Part Number: {p_item.get('part_number')}")
            if p_item.get('description'):
                details.append(f"  - Description: {p_item.get('description')}")
            
            # Handle specifications which is now a list
            specifications = p_item.get('specifications')
            if specifications and isinstance(specifications, list):
                details.append("  - Specifications:")
                for spec in specifications:
                    details.append(f"    - {spec}")
            elif specifications: # Handle if it's a string
                details.append(f"  - Specifications: {specifications}")

            formatted_product_details.append("\n".join(details))
        product_list_for_prompt = "\n\n".join(formatted_product_details)
    else:
        product_list_for_prompt = "No specific product details found, please refer to the overall summary."

    # Format delivery location for the prompt
    location_parts = [delivery_location_obj.get(k) for k in ['street', 'city', 'state', 'zip_code'] if delivery_location_obj.get(k)]
    delivery_location_for_prompt = ", ".join(location_parts) if location_parts else "an unspecified location"

    mission_statement = config.COMPANY_INFO.get("MISSION_STATEMENT", "Our mission is to foster meaningful progress through integrity, innovation, and collaboration.")

    prompt = f"""
    You are a highly professional procurement specialist for "Campsable.com". Your task is to draft a formal, persuasive, and personalized email to a potential supplier to request a quote for a government contract. The email should be concise, professional, and highlight key requirements.

    **Recipient:** {vendor_name}
    **Sender:** {point_of_contact}
    **Our Company Name:** Campsable.com
    **Our Mission Statement:**
    {mission_statement}

    **Solicitation Details:**
    *   **Title:** {title}
    *   **Issuing Agency:** {agency}
    *   **Products/Services Required (Precise Details):**
        {product_list_for_prompt}
    *   **Delivery Location:** {delivery_location_for_prompt}
    *   **Overall Summary of Requirements:**
        {summary}

    **Instructions:**
    1.  The email should be personally addressed to the "{vendor_name} Team".
    2.  The subject line must be compelling and informative: "Partnership Opportunity for Government Contract: {title}".
    3.  The body of the email must be structured, professional, and persuasive. It should include the following sections:
        a. **Introduction:** Briefly introduce "Campsable.com" as a specialist in government contracting. Clearly state that we are preparing a competitive bid for the referenced solicitation with the {agency} and are seeking a reliable supplier for the required products/services. Mention the solicitation title.
        b. **Detailed Opportunity Overview:** Clearly present the "Products/Services Required" and "Delivery Location" information. **For product details (quantities, units, names, descriptions, specifications, part numbers), copy the exact information verbatim as provided in the 'Products/Services Required (Precise Details)' section above. Do NOT rephrase, summarize, or omit any of these product specifics. It is critical that the vendor receives the exact requirements.** Emphasize this as a valuable business opportunity requiring precise fulfillment.
        c. **Our Company's Values:** Briefly incorporate our mission statement or key values to give context to our approach.
        d. **Call to Action:** Request their interest in providing a confidential quote, ask for their capabilities statement or relevant product catalog, and **specifically inquire about their ability to provide shipping to the specified Delivery Location.**
    4.  The email should be signed off by "{point_of_contact}" from "Campsable.com".
    5.  Maintain a professional, confident, and partnership-oriented tone throughout.
    6.  Ensure the email is concise and easy to read, highlighting the most critical information upfront.

    Return the email as a JSON object with two keys: "subject" and "body".
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
