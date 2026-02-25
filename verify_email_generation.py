import sqlite3
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from run_email_campaign import format_email_body

DB_PATH = "rebusiness_automation.db"

def verify_generation():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get a mix of potential Service and Product content
    # We want to see if the auto-detection works
    query = """
    SELECT s.contract_id, s.title, s.analysis_summary, s.data, s.url,
           p.product_name, p.quantity, p.specifications, p.description
    FROM solicitations s
    JOIN products p ON s.contract_id = p.contract_id
    LIMIT 10
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    print(f"Testing {len(rows)} records...")
    
    for row in rows:
        contract_id = row[0]
        title = row[1]
        analysis_json = row[3]
        
        # Check what we expect based on data
        naics = "N/A"
        ai_cat = "N/A"
        if analysis_json:
            try:
                data = json.loads(analysis_json)
                naics = data.get('naics_code')
                ai_cat = data.get('solicitation_category')
            except: pass
            
        print("-" * 60)
        print(f"ID: {contract_id}")
        print(f"Title: {title}")
        print(f"NAICS: {naics} | AI Category: {ai_cat}")
        
        subject, body, html = format_email_body(
            sol_id=row[0],
            sol_title=row[1],
            product_name=row[5],
            quantity=row[6],
            specs=row[7],
            delivery_loc_json=None,
            timeline=None,
            description=row[8],
            due_date_str=None,
            sol_url=row[4],
            analysis_json=row[3]
        )
        
        # Determine what category was chosen based on unique strings in the body
        # Service email has: "Scope of Work"
        # Product email has: "Items Required" and "Manufacturer CAGE"
        
        detected = "UNKNOWN"
        if "Items Required" in body and "Manufacturer CAGE" in body:
            detected = "Product"
        elif "Scope of Work" in body:
            detected = "Service"
            
        print(f"Generating Email -> DETECTED CATEGORY: {detected}")
        
        # Verification Logic
        if str(naics).startswith(('31','32','33')):
            if detected != "Product":
                 # Check if overridden by Service keywords
                 if any(x in title.lower() for x in ['repair', 'service', 'maintenance']):
                     print("✅ Correctly overridden to Service by keywords")
                 else:
                     print("❌ MISMATCH: NAICS is Product but generated Service")
            else:
                print("✅ Match (NAICS Product)")
        else:
            # Default is Service, so unless keywords say Product...
            print(f"ℹ️  Non-Mfg NAICS. Result: {detected}")

    conn.close()

if __name__ == "__main__":
    verify_generation()
