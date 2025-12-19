import os
import config
import google.genai as genai
from google.genai.types import HttpOptions

# Configure the generative AI model with the API key from our config file
client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=HttpOptions(api_version="v1"))

# Create the generative model


def find_vendors(solicitation_analysis):
    """
    Finds vendors based on the analysis of a solicitation using the generative model.

    Args:
        solicitation_analysis (str): The text analysis of the solicitation.

    Returns:
        str: The text response from the generative model containing a list of potential vendors.
    """
    # We are creating a prompt that instructs the model to act as a vendor scout.
    prompt = f"""
    You are a 'Vendor Scout Agent'. Your task is to find potential vendors for a government contract.
    Based on the following solicitation analysis, find a list of suitable vendors.
    For each vendor, provide their name, website, and a brief justification for why they are a good fit.

    **Solicitation Analysis:**
    {solicitation_analysis}
    """

    # Send the prompt to the model
    response = client.models.generate_content(model='models/gemini-2.5-flash', contents=prompt)

    # In a real implementation, you would parse this response to a structured list of vendors.
    # For now, we will return the raw text response.
    return response.text

if __name__ == "__main__":
    # Example solicitation analysis (in a real workflow, this would come from the SolicitationAnalysisAgent)
    example_analysis = """
    - Solicitation Title: Temporary Portable Steel Logging Bridge
    - Key Requirements: 40-foot portable steel bridge for logging operations, must be delivered to the Andrew Pickens Ranger District in South Carolina.
    """
    print(f"--- Running VendorScoutAgent for the following analysis: ---\n{example_analysis}")
    vendors = find_vendors(example_analysis)
    print("\n--- Vendor Scout Results ---")
    print(vendors)
