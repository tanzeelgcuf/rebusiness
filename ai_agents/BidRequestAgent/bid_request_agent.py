import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import config

def create_bid_request_body(solicitation_title, analysis_summary):
    """
    Generates a bid request email body using an LLM, based on the solicitation analysis.

    Args:
        solicitation_title (str): The title of the solicitation.
        analysis_summary (str): The detailed analysis of the solicitation.

    Returns:
        str: The generated email body for the bid request.
    """
    
    prompt = f"""
    You are an expert in procurement and supply chain management. Your task is to generate a concise and professional bid request email to a potential vendor.

    Use the following information:
    - Solicitation Title: {solicitation_title}
    - Summary of Requirements (from analysis of solicitation documents): {analysis_summary}

    Generate an email body with the following structure:
    1.  A polite and professional opening.
    2.  A clear statement that we are preparing a proposal for the specified solicitation title.
    3.  A "Summary of Requirements" section that clearly lists the key products or services needed, based on the provided summary.
    4.  A direct question asking if the vendor would be interested in providing a quote for these requirements.
    5.  A professional closing from "The Rebusiness Automation Project Team".

    The email should be clear, concise, and professional.
    """

    try:
        if config.LLM_PROVIDER == "openai":
            from openai import OpenAI
            client_openai = OpenAI(api_key=config.OPENAI_API_KEY)
            response = client_openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a procurement assistant that writes professional bid requests to vendors."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        else: # Default to gemini
            import google.generativeai as genai
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            response = client.generate_content(prompt)
            return response.text
    except Exception as e:
        print(f"Error during LLM bid request generation: {e}")
        # Fallback to a simple template if LLM fails
        return f"""Dear Vendor,

We are preparing a proposal for the solicitation '{solicitation_title}' and are looking for potential suppliers.

Based on our analysis, the key requirements are:
{analysis_summary}

Would your company be interested in providing a quote for these requirements?

Thank you,
The Rebusiness Automation Project Team
"""
