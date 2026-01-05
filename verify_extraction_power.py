
import os
import json
import logging
from ai_agents.SAMGovExtractor.sam_gov_extractor import SAMGovExtractor

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_extraction_power():
    extractor = SAMGovExtractor()
    
    test_cases = [
        {
            "name": "Service Case (Medical Physicist)",
            "file": "temp_36C25626Q0007_Gulf_Coast_Medical_Physicist_and_Radiation_Safety_Officer_Services.html",
            "expected_category": "Service"
        },
        {
            "name": "Product Case (Bearing Sleeve)",
            "file": "temp_SPE4A626RX266_3120013722735_Bearing_Sleeve_Part_4080903.html",
            "expected_category": "Product"
        }
    ]
    
    results = []
    
    for case in test_cases:
        file_path = os.path.join(os.getcwd(), case["file"])
        if not os.path.exists(file_path):
            print(f"⚠️ Skipping {case['name']} - File not found: {case['file']}")
            continue
            
        print(f"\n--- Testing: {case['name']} ---")
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        # Run extraction
        data = extractor.extract_solicitation(html_content)
        
        # Check category
        detected_cat = data.get('solicitation_category')
        status = "✅ PASS" if detected_cat == case["expected_category"] else "❌ FAIL"
        print(f"Result: {status} (Expected: {case['expected_category']}, Found: {detected_cat})")
        
        # Check for placeholders
        placeholders = []
        def find_placeholders(d, path=""):
            if isinstance(d, dict):
                for k, v in d.items():
                    find_placeholders(v, f"{path}.{k}")
            elif isinstance(d, list):
                for i, v in enumerate(d):
                    find_placeholders(v, f"{path}[{i}]")
            else:
                if any(p in str(d).lower() for p in ["see solicitation", "as per", "refer to"]):
                    placeholders.append(f"{path}: {d}")
        
        find_placeholders(data)
        if placeholders:
            print(f"⚠️ Found {len(placeholders)} possible placeholders:")
            for p in placeholders[:5]: print(f"  - {p}")
        else:
            print("✅ ZERO Placeholders detected in critical fields!")

        # Print some high-fidelity fields
        print("\n--- High-Fidelity Data Samples ---")
        if detected_cat == "Service":
            print(f"Insurance: {json.dumps(data.get('key_requirements', {}).get('insurance_requirements'), indent=2)}")
            print(f"Legal Bans: {data.get('legal_clauses', {}).get('prohibited_technologies')}")
        else:
            print(f"Packaging: {data.get('packaging_requirements', {}).get('preservation_level')}")
            print(f"DPAS: {data.get('overview', {}).get('dpas_rating')}")
            
        results.append(data)
        
    return results

if __name__ == "__main__":
    test_extraction_power()
