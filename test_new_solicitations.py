import os
import shutil
import datetime
from database_manager import DatabaseManager
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent

# Setup
SOL_DIR = "data/solicitations"
db = DatabaseManager()
reader = AttachmentReaderAgent()

def setup_case(case_id, title, description, url):
    # 1. Clear/Create Directory
    case_path = os.path.join(SOL_DIR, case_id)
    if os.path.exists(case_path):
        shutil.rmtree(case_path)
    os.makedirs(case_path, exist_ok=True)
    
    # 2. Write Description
    with open(os.path.join(case_path, "description.txt"), "w") as f:
        f.write(description)
        
    # 3. Add to DB
    print(f"Setting up DB for {case_id}...")
    # def add_solicitation(self, contract_id, url, title, description, location, product_requirements, analysis_summary, data):
    db.add_solicitation(
        case_id, 
        url, 
        title, 
        description, 
        "Test Location, USA", 
        None, 
        None, 
        "{}"
    )

def run_test():
    print("=== STARTING PRODUCT & SERVICE GENERATION TEST ===")
    
    # --- CASE 1: PRODUCT ---
    prod_id = "TEST_PRODUCT_NEW_01"
    prod_desc = """
    COMBINED SYNOPSIS/SOLICITATION for Commercial Items.
    Title: Supply of Hydraulic Pump Assemblies
    Solicitation Number: W912AB-26-Q-0001
    
    The US Army Corps of Engineers requires the purchase of Hydraulic Pump Assemblies.
    Quantity: 25 Units.
    Part Number: HPA-5000-X.
    Manufacturer: Industrial Pump Corp or Equal.
    
    Specifications:
    - Max Pressure: 5000 PSI
    - Flow Rate: 50 GPM
    - Power: 480V 3-Phase
    
    Shipping to: Vicksburg, MS 39180.
    
    Response Date: Quotes are due by February 15, 2026 at 10:00 AM EST.
    Email quotes to: contracting@usace.army.mil
    """
    setup_case(prod_id, "Hydraulic Pump Supply", prod_desc, f"http://test/{prod_id}")
    
    print(f"\n--- Running Generation for {prod_id} (Expected: PRODUCT) ---")
    res_prod = reader.create_summary_report(prod_id)
    if "rfq_content" in res_prod:
        with open(f"{prod_id}_RFQ.md", "w") as f:
            f.write(res_prod["rfq_content"])
        print(f"Saved {prod_id}_RFQ.md")
    print("Result:", res_prod)

    # --- CASE 2: SERVICE ---
    svc_id = "TEST_SERVICE_NEW_01"
    svc_desc = """
    PERFORMANCE WORK STATEMENT (PWS)
    Title: Janitorial and Custodial Services
    Solicitation Number: GS-05-P-26-XXXX
    
    The General Services Administration (GSA) has a requirement for janitorial services at the Federal Building in Chicago, IL.
    
    Scope of Work:
    The Contractor shall provide all management, supervision, labor, materials, supplies, and equipment necessary to provide custodial services.
    
    Tasks include:
    - Daily cleaning of restrooms, breakrooms, and office spaces.
    - Weekly floor buffing and waxing.
    - Semi-annual window washing (interior and exterior).
    - Trash removal and recycling management.
    
    Period of Performance:
    Base Period: March 1, 2026 through February 28, 2027.
    Option Year 1: March 1, 2027 through February 29, 2028.
    
    Responses due: March 10, 2026 by 5:00 PM CST.
    """
    setup_case(svc_id, "Janitorial Services Chicago", svc_desc, f"http://test/{svc_id}")
    
    print(f"\n--- Running Generation for {svc_id} (Expected: SERVICE) ---")
    res_svc = reader.create_summary_report(svc_id)
    if "rfq_content" in res_svc:
        with open(f"{svc_id}_RFQ.md", "w") as f:
            f.write(res_svc["rfq_content"])
        print(f"Saved {svc_id}_RFQ.md")
    print("Result:", res_svc)

if __name__ == "__main__":
    run_test()
