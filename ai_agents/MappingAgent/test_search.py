import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from ai_agents.MappingAgent.mapping_agent import MappingAgent

def test_google_search():
    agent = MappingAgent()
    vendor_name = "Boeing Distribution Services"
    print(f"Testing Google search for: {vendor_name}")
    try:
        # Force the agent to use Selenium by ensuring SerpAPI mock returns nothing if it was called (though we are calling the selenium method directly)
        url, linkedin = agent._google_search_for_website_selenium(vendor_name)
        print(f"Result URL: {url}")
        print(f"Result LinkedIn: {linkedin}")
    except Exception as e:
        print(f"Test failed with error: {e}")
    finally:
        agent.close()

if __name__ == "__main__":
    test_google_search()
