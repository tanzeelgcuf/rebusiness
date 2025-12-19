import json

def summarize_solicitations(file_path):
    """
    Reads solicitation details from a JSON file and generates a summary.
    """
    try:
        with open(file_path, 'r') as f:
            solicitations = json.load(f)
    except FileNotFoundError:
        return "Error: Solicitation details file not found."
    except json.JSONDecodeError:
        return "Error: Could not decode JSON from solicitation details file."

    if not solicitations:
        return "No solicitations found to summarize."

    summary_parts = []
    summary_parts.append(f"Summary of {len(solicitations)} Solicitations for NAICS 238220:\n")

    for i, sol in enumerate(solicitations):
        title = sol.get('solicitation_title', 'N/A')
        notice_id = sol.get('notice_id', 'N/A')
        published_date = sol.get('published_date', 'N/A')
        date_offers_due = sol.get('date_offers_due', 'N/A')
        department_agency = sol.get('department_agency', 'N/A')
        description = sol.get('description', 'No description provided.')
        url = sol.get('url', 'N/A') # Assuming URL is part of the details now

        summary_parts.append(f"--- Solicitation {i+1} ---")
        summary_parts.append(f"Title: {title}")
        summary_parts.append(f"Notice ID: {notice_id}")
        summary_parts.append(f"Published Date: {published_date}")
        summary_parts.append(f"Offers Due: {date_offers_due}")
        summary_parts.append(f"Department/Agency: {department_agency}")
        summary_parts.append(f"Description: {description[:200]}...") # Truncate description for summary
        summary_parts.append(f"URL: {url}\n")

    return "\n".join(summary_parts)

def generate_email_proposal(summary):
    """
    Generates a draft email proposal based on the summary of solicitations.
    """
    email_template = f"""Subject: Proposal for NAICS 238220 Opportunities - [Your Company Name]

Dear [Hiring Manager/Relevant Contact],

I hope this email finds you well.

Our company, [Your Company Name], specializes in [Your Company's Core Competencies, e.g., Plumbing, Heating, and Air-Conditioning services]. We have identified several upcoming opportunities under NAICS code 238220 that align perfectly with our expertise and capabilities.

Below is a summary of the relevant solicitations we've identified:

{summary}

We are confident that our team possesses the necessary skills, experience, and resources to successfully execute these projects. We are particularly interested in [mention a specific type of project or agency if applicable].

We would appreciate the opportunity to discuss our qualifications further and explore how we can contribute to your mission. Please let us know if you are available for a brief call at your convenience.

Thank you for your time and consideration.

Sincerely,

[Your Name]
[Your Title]
[Your Company Name]
[Your Contact Information]
"""
    return email_template

if __name__ == "__main__":
    details_file = "solicitation_details_238220.json"
    
    solicitation_summary = summarize_solicitations(details_file)
    print(solicitation_summary)

    email_proposal = generate_email_proposal(solicitation_summary)
    print("\n--- DRAFT EMAIL PROPOSAL ---")
    print(email_proposal)

    # Optionally save the email to a file
    with open("email_proposal_238220.md", "w") as f:
        f.write(email_proposal)
    print("\nDraft email proposal saved to email_proposal_238220.md")
