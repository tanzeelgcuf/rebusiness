from ai_agents.GmailAgent.gmail_agent import GmailAgent
import json

def run_test_gmail():
    print("Attempting to create a test Gmail draft...")
    gmail_agent = GmailAgent()
    
    test_to = "your_email@example.com" # Replace with an actual email address for testing
    test_subject = "Test Draft from Rebusiness Agent - Authentication Check"
    test_body = """
    This is a test draft created by the Rebusiness Automation system to verify Gmail API authentication.
    If you see this draft in your Gmail, the authentication was successful!
    """
    
    draft = gmail_agent.create_draft(to=test_to, subject=test_subject, body=test_body)
    
    if draft:
        print("\nSuccessfully created a test draft. Please check your Gmail drafts folder.")
        print("Once you've confirmed, you can delete 'test_gmail.py' and 'token.json'.")
    else:
        print("\nFailed to create a test draft. Please check the console for errors.")

if __name__ == "__main__":
    run_test_gmail()

