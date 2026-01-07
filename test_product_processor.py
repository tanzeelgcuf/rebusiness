
import sys
import os
import json
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from ai_agents.ProductProcessor.product_processor import EnhancedProductProcessor
from database_manager import DatabaseManager

# Mock DB Manager that returns file-based analysis for N00104
class MockDBManager:
    def get_analysis_by_contract_id(self, contract_id):
        # Determine path to stored analysis
        # In previous steps, AttachmentReaderAgent saved analysis to data/solicitations/...
        # But wait, did it? "Reader saved analysis" is in the log.
        # Let's check if the file exists, otherwise we mock it from N00104_guide_output_final.md context
        # Actually, the previous 're_process_n00104.py' script ran AttachmentReaderAgent.
        # It should have produced a JSON analysis.
        # Check 'N0010425QNF13' dir.
        
        path = f"data/solicitations/{contract_id}/analysis.json"
        
        # If file doesn't exist, we might need to rely on what we know or run the reader.
        # But let's assume valid JSON exists or create a mock one resembling the extraction we just verified.
        
        if os.path.exists(path):
            with open(path, 'r') as f:
                return {'analysis_json': f.read()}
        
        # Fallback Mock Data based on our successful extraction
        print(f"DEBUG: Analysis file not found at {path}, using MOCK data.")
        mock_data = {
            "notice_id": "N00104-25-Q-NF13",
            "title": "CABLE ASSEMBLY,SPEC",
            "description": "Repair of Cable Assembly.",
            "solicitation_number": "N00104-25-Q-NF13",
            "contract_type": "Repair Service",
            "specifications": {
                "nsn": "5995-01-604-0910",
                "manufacturer_cage": "Unknown", 
                "quantity": "2",
                "description": "Repair services for Cable Assembly"
            },
            "clins": [
                {"clin": "0001", "description": "CABLE ASSEMBLY,SPEC", "quantity": "2", "unit": "EA", "notes": "Repair Service"}
            ],
            "delivery_requirements": {
                "lead_time_days": "120",
                "fob_point": "Origin"
            },
            "submission": {
                "due_date": "2025-02-28"
            }
        }
        return {'analysis_json': json.dumps(mock_data)}

def test_processor():
    logging.basicConfig(level=logging.INFO)
    contract_id = "N0010425QNF13" # The ID used in the DB/Folder structure usually normalized
    
    print(f"Testing EnhancedProductProcessor on {contract_id}...")
    
    # 1. Check if folder exists
    if not os.path.exists(f"data/solicitations/{contract_id}"):
        # Try with hyphens? 
        if os.path.exists(f"data/solicitations/N00104-25-Q-NF13"):
            contract_id = "N00104-25-Q-NF13"
        else:
             print("Warning: Solicitation folder not found, mock DB will handle data but saving might fail if dir missing.")
             os.makedirs(f"data/solicitations/{contract_id}", exist_ok=True)

    db = MockDBManager()
    processor = EnhancedProductProcessor(db)
    
    # Test text classification logic specifically
    print("\n--- Testing Classification Logic ---")
    test_text = "Repair of CABLE ASSEMBLY,SPEC. NSN: 5995-01-604-0910. CAGE Code required."
    is_prod = processor.is_product_solicitation(test_text)
    print(f"Text: '{test_text}'")
    print(f"Classified as Product? {is_prod} (Expect True due to Repair+NSN override)")
    
    # Run Full Process
    print("\n--- Running Process ---")
    rfq = processor.process_and_generate_vendor_rfq(contract_id)
    
    if rfq:
        print("\nSUCCESS: RFQ Generated!")
        print("First 500 chars:")
        print(rfq[:500])
    else:
        print("\nFAILURE: No RFQ generated (or classified as Service).")

if __name__ == "__main__":
    test_processor()
