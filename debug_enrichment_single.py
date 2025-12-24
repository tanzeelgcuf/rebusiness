
import logging
import json
import sys
import os
sys.path.append(os.path.abspath('ai_agents'))

from data_enrichment import DataEnricher

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugEnricher")

def debug_single(contract_id, url=None):
    enricher = DataEnricher()
    
    print(f"--- Debugging Enrichment for {contract_id} ---")
    
    # Force enrichment
    result = enricher.enrich_contract(contract_id, url)
    
    print("\n\n--- RAW RESULT ---")
    print(json.dumps(result, indent=2))
    
    # Diagnose extraction
    print("\n--- DIAGNOSIS ---")
    if not result:
        print("RESULT IS NONE/EMPTY")
        return

    # 1. Description
    desc = result.get('summary') # Default
    prod_desc = None
    if result.get('product_details'):
        prod_desc = result['product_details'][0].get('description')
    
    print(f"Summary: {desc}")
    print(f"Product[0] Description: {prod_desc}")
    
    # 2. Quantity
    qty = None
    if result.get('product_details'):
        qty = result['product_details'][0].get('quantity')
    print(f"Quantity: {qty}")
    
    # 3. Location
    loc = result.get('delivery_location')
    print(f"Location: {loc}")
    
    # 4. Timeline
    time = result.get('delivery_timeline')
    print(f"Timeline: {time}")

if __name__ == "__main__":
    # SAM-CNLES is the problematic one
    # We might need a URL if it's not in DB, but DataEnricher should handle it if passed or found
    # Using a search URL as fallback like the main script does
    cid = "SAM-CNLES" 
    # Use the URL logic from the script
    url = f"https://sam.gov/search/?index=opp&page=1&sort=-modifiedDate&pageSize=25&sfm%5BsimpleSearch%5D%5BkeywordRadio%5D=ALL&sfm%5BsimpleSearch%5D%5BkeywordTags%5D={cid}"
    
    debug_single(cid, url)
