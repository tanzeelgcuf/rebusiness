from ai_agents.ResponseAgent.response_agent import ResponseAgent
import logging

logging.basicConfig(level=logging.INFO)

def test_logic():
    agent = ResponseAgent()
    
    # Test 1: Quote
    subject = "Quote for Industrial Bolts - Ref 12345"
    body = "Hi John, Please find attached our quote for the 500 units you requested. Price is $5/unit. Lead time 2 weeks. Thanks, Supplier A"
    
    print("\n--- Test 1: Quote ---")
    res = agent.classify_email(subject, body)
    print(res)

    # Test 2: Question
    subject = "Clarification needed: MMU Dimensions"
    body = "Hello, regarding your RFQ for the Mobile Medical Unit. Do you need the interior refurbished as well, or just the exterior paint? Regards, Supplier B"
    
    print("\n--- Test 2: Question ---")
    res = agent.classify_email(subject, body)
    print(res)
    
    # Test 3: Spam
    subject = "Boost your SEO today"
    body = "Hi, we can get you to #1 on Google. Click here."
    
    print("\n--- Test 3: Spam ---")
    res = agent.classify_email(subject, body)
    print(res)

if __name__ == "__main__":
    test_logic()
