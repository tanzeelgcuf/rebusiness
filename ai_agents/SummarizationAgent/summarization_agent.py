import os
import sys
import config
import google.genai as genai
from google.genai.types import HttpOptions

# Add the parent directory to the Python path to allow imports from other agent directories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Configure the generative AI model with the API key from our config file
client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=HttpOptions(api_version="v1"))

def summarize_solicitation(solicitation_details):
    """
    Summarizes the key information from a solicitation's details, including attachments.

    Args:
        solicitation_details (dict): A dictionary containing the scraped solicitation details.

    Returns:
        str: A summary of the solicitation.
    """
    description = solicitation_details.get("description", "No description provided.")
    attachments = solicitation_details.get("attachments", [])

    attachments_info = ""
    if attachments:
        attachments_info = "\n\nAttached Files:\n"
        for attachment in attachments:
            attachments_info += f"- {attachment.get('title', 'N/A')}: {attachment.get('url', 'N/A')}\n"

    prompt = f"""
    You are a 'Summarization Agent'. Your task is to provide a concise summary of the following government contract solicitation.
    Focus on the key requirements, important dates, and any critical information for a potential bidder.

    Solicitation Title: {solicitation_details.get('solicitation_title', 'N/A')}
    Published Date: {solicitation_details.get('published_date', 'N/A')}
    Date Offers Due: {solicitation_details.get('date_offers_due', 'N/A')}
    NAICS Code: {solicitation_details.get('naics_code', 'N/A')}
    Place of Performance: {solicitation_details.get('place_of_performance', 'N/A')}

    Description:
    {description}
    {attachments_info}

    Please provide a summary that is easy to understand and highlights actionable insights for a business looking to bid.
    """

    # Send the prompt to the model
    response = client.models.generate_content(model='models/gemini-2.5-flash', contents=prompt)

    return response.text

if __name__ == "__main__":
    # Example usage
    example_solicitation_details = {
        "solicitation_title": "Example Plumbing Services Contract",
        "url": "http://example.com/solicitation/123",
        "notice_id": "ABC-123",
        "published_date": "2025-10-26",
        "date_offers_due": "2025-11-15",
        "naics_code": "238220",
        "place_of_performance": "Anytown, USA",
        "description": "This is a contract for plumbing services including repair, maintenance, and installation of water systems in government buildings. Bidders must have experience with large-scale commercial plumbing projects.",
        "primary_poc": {"name": "Jane Doe", "email": "jane.doe@example.gov"},
        "attachments": [
            {"title": "Scope of Work.pdf", "url": "http://example.com/sow.pdf"},
            {"title": "Pricing Sheet.xlsx", "url": "http://example.com/pricing.xlsx"}
        ]
    }
    summary = summarize_solicitation(example_solicitation_details)
    print("\n--- Solicitation Summary ---")
    print(summary)
