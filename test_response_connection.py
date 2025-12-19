from ai_agents.ResponseAgent.response_agent import ResponseAgent
import logging

logging.basicConfig(level=logging.INFO)

def test_conn():
    print("Initializing Agent...")
    agent = ResponseAgent()
    
    print("Checking connection (PEEK mode)...")
    # We access the monitor directly
    emails = agent.monitor.check_for_emails(peek=True)
    
    print(f"Connection Successful.")
    print(f"Found {len(emails)} unread emails.")
    
    if emails:
        print("First email subject:", emails[0]['subject'])
        print("First email from:", emails[0]['from'])

if __name__ == "__main__":
    test_conn()
