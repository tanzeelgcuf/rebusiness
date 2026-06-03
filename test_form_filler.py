import sys
import os
import logging

# Add path to allow import
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ai_agents.OutreachAgent.form_filler import FormFiller

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    filler = FormFiller()
    
    # Test Data (Atlas Bolt)
    target_url = "https://www.atlasbolt.com"
    test_data = {
        "name": "John Campbell",
        "email": "bobbysmitty078@gmail.com",
        "message": "Hello, this is a test inquiry about availability.",
        "subject": "Quote Request",
        "company": "CampSable LLC"
    }
    
    print(f"Testing Form Filler on {target_url}...")
    result = filler.fill_form(target_url, test_data)
    print("---------------------------------------------------")
    print(f"Fill Success: {result['success']}")
    print(f"Extracted Emails: {result['extracted_emails']}")
    print(f"Error: {result['error']}")
    print("---------------------------------------------------")
