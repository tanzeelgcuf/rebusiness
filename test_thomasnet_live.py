import sys
import os

# Add parent directory to path to import ai_agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
from ThomasNetAgent.thomasnet_agent import ThomasNetAgent

def test_live_search():
    print("=== Testing ThomasNetAgent Live Search ===")
    agent = ThomasNetAgent()
    
    product_name = "Industrial HVAC Systems"
    print(f"Searching for: {product_name}")
    
    suppliers = agent.find_suppliers_for_product({'product_name': product_name})
    
    print(f"\nFound {len(suppliers)} suppliers:")
    for s in suppliers:
        print(f" - Name: {s['name']}")
        print(f"   Website: {s['website']}")
        print(f"   Source: {s.get('source')}")
        print("---")
        
    if suppliers:
        print("\nSUCCESS: Vendors found via ThomasNet.")
    else:
        print("\nFAILURE: No vendors found.")

if __name__ == "__main__":
    test_live_search()
