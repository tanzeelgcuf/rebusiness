
import logging
import sys
import os
import json

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_category_selection():
    print("--- Testing Template Selection Logic ---\n")
    
    scenarios = [
        {
            "title": "Maintenance of HVAC Systems",
            "naics": "561210", 
            "expected": "Service",
            "reason": "Keyword 'Maintenance' + NAICS 56"
        },
        {
            "title": "Supply of 5000 PSI Water Pumps",
            "naics": "333914",
            "expected": "Product",
            "reason": "NAICS 33 (Manufacturing) + Keyword 'Supply'"
        },
        {
            "title": "Repair Services for Elevators",
            "naics": None,
            "expected": "Service",
            "reason": "Keyword 'Repair Services'"
        },
        {
            "title": "Hardware Delivery for IT Dept",
            "naics": None,
            "expected": "Product",
            "reason": "Keyword 'Hardware' + 'Delivery'"
        },
        {
            "title": "Janitorial Labor and Cleaning",
            "naics": "561720",
            "expected": "Service",
            "reason": "Keyword 'Labor' + NAICS 56"
        },
        {
            "title": "Ambiguous Requirement",
            "naics": "999999",
            "expected": "Service", # Default
            "reason": "Default Fallback"
        }
    ]
    
    for s in scenarios:
        title = s['title']
        naics = s['naics']
        expected = s['expected']
        
        # Simulate logic from run_email_campaign.py
        category = "Service" # Default
        
        # 1. NAICS
        if naics and str(naics).startswith(('31', '32', '33')):
            category = "Product"
            
        # 2. Strong Keywords (Service) - Overrides NAICS if ambiguous
        if any(x in title.lower() for x in ['maintenance', 'service', 'installation', 'repair', 'labor', 'rental']):
            category = "Service"
        # 3. Product Keywords (only if not already Service from step 2)
        elif any(x in title.lower() for x in ['supply', 'deliver', 'hardware', 'equipment', 'parts', 'software', 'license']):
            category = "Product"
        
        result = "PASSED" if category == expected else "FAILED"
        print(f"[{result}] Title: '{title}' (NAICS: {naics}) -> Detected: {category} (Expected: {expected})")

if __name__ == "__main__":
    test_category_selection()
