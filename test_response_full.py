from ai_agents.ResponseAgent.response_agent import ResponseAgent
import logging
import sqlite3

logging.basicConfig(level=logging.INFO)

# Mock sender to avoid sending real email
def mock_send(to, subject, body):
    print(f"--> [MOCK SEND] To: {to} | Subj: {subject}")
    print(f"    Body: {body[:50]}...")
    return True

def test_full_flow():
    agent = ResponseAgent()
    # Override sender
    agent.sender.send_email = mock_send
    
    # Mock Email Data from Airhardware
    email_data = {
        'from': 'Mark <mswiech@airhardware.com>',
        'subject': 'Quote for Bolts',
        'body': 'Here is the quote you asked for.'
    }
    
    analysis = {
        'category': 'QUOTE_RECEIVED'
    }
    
    print("Simulating Quote Handling...")
    agent.handle_quote(email_data, analysis)
    
    # Verify DB update
    conn = sqlite3.connect("rebusiness_automation.db")
    cur = conn.cursor()
    cur.execute("SELECT id, status, response_date FROM manufacturer_requests WHERE manufacturer_id=19 ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    
    if row:
        print(f"\nDB Verification: ID={row[0]}, Status={row[1]}, ResponseDate={row[2]}")
        if row[1] == 'replied':
            print("SUCCESS: Status updated to 'replied'.")
        else:
            print("FAILURE: Status not updated.")
    else:
        print("FAILURE: Request not found in DB.")

if __name__ == "__main__":
    test_full_flow()
