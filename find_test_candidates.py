
import sys
import os
import logging
import time

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent

# Configure logging to suppress noise
logging.basicConfig(level=logging.ERROR)

BURNED_IDS = [
    'c79f3275bb094cfdafc99a3c5225ed44', # Product (Trailer)
    '76f56419dbf040faa7ba6a085a9497ab', # Service (Janitorial)
    '525770dd89c24468b4fc152c8b9227f4'  # Previous Product
]

def find_candidates():
    print("Initializing SamGovAgent...")
    agent = SamGovAgent()
    try:
        agent.start_browser()
        
        # Product Search
        print("\n--- Searching for PRODUCT candidate (keyword: 'lumber') ---") 
        product_links = agent.search_for_links("lumber", start_page=1, num_pages=1)
        
        found_prod = False
        for link in product_links:
            if not any(bid in link for bid in BURNED_IDS):
                print(f"FOUND NEW PRODUCT URL: {link}")
                found_prod = True
                break
        if not found_prod:
            print("No new product links found.")

        # Service Search
        print("\n--- Searching for SERVICE candidate (keyword: 'landscaping') ---") 
        service_links = agent.search_for_links("landscaping", start_page=1, num_pages=1)
        
        found_serv = False
        for link in service_links:
            if not any(bid in link for bid in BURNED_IDS):
                print(f"FOUND NEW SERVICE URL: {link}")
                found_serv = True
                break
        if not found_serv:
            print("No new service links found.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if agent:
            # properly close if exists
            try:
                agent.context.close()
                agent.browser.close()
            except: pass

if __name__ == "__main__":
    find_candidates()
