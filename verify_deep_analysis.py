import os
import shutil
import json
from ai_agents.SolicitationAnalysisAgent.solicitation_analysis import analyze_solicitation

def verify_deep_analysis():
    print("--- TEST: Deep Analysis Integration ---")
    
    # 1. Setup Mock Data
    contract_id = "TEST_DEEP_001"
    base_dir = f"data/solicitations/{contract_id}"
    
    # Cleanup old test
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
    
    os.makedirs(os.path.join(base_dir, "attachments"))
    os.makedirs(os.path.join(base_dir, "linked_pages"))
    
    print(f"Created mocked directory: {base_dir}")
    
    # Source A: Description (Vague)
    desc = "We need some specialized pumps. See attachments for details. Also check the manufacturer site linked below."
    with open(os.path.join(base_dir, "description.txt"), "w") as f:
        f.write(desc)
        
    # Source B: Attachment (Specific Specs)
    with open(os.path.join(base_dir, "attachments", "specs.txt"), "w") as f:
        f.write("SPECIFICATION SHEET:\n- Flow Rate: 500 GPM\n- Material: Stainless Steel 316\n- Compliance: ISO 9001")
        
    # Source C: Linked Page (Brand Name)
    with open(os.path.join(base_dir, "linked_pages", "manufacturer_site.txt"), "w") as f:
        f.write("Source: http://pump-maker.com\n\nOur flagship model is the 'X-Series Turbo Pump'. It is the industry standard.")
        
    # 2. Run Analysis
    print("Running analysis...")
    sol_dict = {
        'contract_id': contract_id,
        'description': desc
    }
    
    # This should trigger the deep reading logic
    text, confidence = analyze_solicitation(sol_dict)
    
    print(f"Analysis Complete. Confidence: {confidence}")
    print("Raw Output Snippet:", text[:500])
    
    # 3. Validation
    # We check if the unique info from attachments and links made it into the JSON
    
    failures = []
    
    if "500 GPM" not in text:
        failures.append("❌ Missing Attachment Data (500 GPM)")
    else:
        print("✅ Found Attachment Data (500 GPM)")
        
    if "X-Series Turbo Pump" not in text:
        failures.append("❌ Missing Linked Page Data (X-Series Turbo Pump)")
    else:
        print("✅ Found Linked Page Data (X-Series Turbo Pump)")
        
    if "thomasnet_search_terms" not in text:
         failures.append("❌ Missing 'thomasnet_search_terms' key")
    else:
        print("✅ Found 'thomasnet_search_terms'")

    if failures:
        print("\nTest FAILED:")
        for f in failures:
            print(f)
    else:
        print("\nSUCCESS: Deep Analysis working correctly.")

if __name__ == "__main__":
    verify_deep_analysis()
