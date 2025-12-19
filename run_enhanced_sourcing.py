import sys
import asyncio
import os
import json
from database_manager import DatabaseManager
from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent
from ai_agents.OutreachAgent.form_filler import FormFiller

# Config
LIMIT_SUPPLIERS = 40

async def run_enhanced_workflow():
    print("=== Starting Enhanced Sourcing & Outreach Workflow ===")
    print(f"Goal: {LIMIT_SUPPLIERS} suppliers per product. Identity: John Campbell.")
    
    db = DatabaseManager()
    tn_agent = ThomasNetAgent()
    outreach_agent = FormFiller()
    
    # 1. Fetch Candidates (Products with 'pending' sourcing status)
    # Using direct query if wrapper doesn't exist
    conn = db._connect_db()
    cursor = conn.cursor()
    
    # Get products that haven't been fully sourced yet
    # We join with sourcing status to filter
    query = """
        SELECT p.id, p.product_name, s.solicitation_number, s.response_deadline 
        FROM products p
        JOIN solicitations s ON p.solicitation_id = s.id
        LEFT JOIN product_sourcing_status pss ON p.id = pss.product_id
        WHERE pss.status IS NULL OR pss.status = 'pending'
        LIMIT 5
    """
    products = cursor.execute(query).fetchall()
    conn.close()
    
    print(f"Found {len(products)} products pending sourcing.")
    
    for row in products:
        p_id = row[0]
        p_name = row[1]
        sol_num = row[2]
        due_date = row[3]
        
        print(f"\n>>> Processing Product: {p_name} (ID: {p_id})")
        db.update_sourcing_status(p_id, 'sourcing')
        
        # 2. Find Suppliers (ThomasNet)
        # Using the agent DIRECTLY (Python API) instead of subprocess for better control
        suppliers_found = tn_agent.find_suppliers_for_product({'product_name': p_name}, limit=LIMIT_SUPPLIERS)
        
        print(f"Found {len(suppliers_found)} suppliers via ThomasNet.")
        
        # 3. Outreach (Iterate and Engage)
        engaged_count = 0
        for supplier in suppliers_found:
            supplier_url = supplier['website']
            company_name = supplier['name']
            
            # Save basic supplier info first
            m_id = db.add_manufacturer(
                name=company_name,
                website=supplier_url,
                address=supplier.get('location')
            )
            db.link_product_supplier(p_id, m_id)
            
            if not supplier_url:
                print(f"  Skipping outreach for {company_name} (No URL)")
                continue

            # Engage
            print(f"  Engaging {company_name} at {supplier_url}...")
            
            product_details = {
                'product_name': p_name,
                'notice_id': sol_num,
                'due_date': due_date,
                'quantity': "See attached/linked solicitation"
            }
            
            try:
                result = await outreach_agent.process_supplier_outreach(supplier_url, product_details)
                
                # Log outcome
                print(f"    Outcome: Form={result['form_filled']}, Emails Sent={result['emails_sent']}")
                if result['error']:
                    print(f"    Error: {result['error']}")
                
                engaged_count += 1
                
            except Exception as e:
                print(f"    Outreach failed: {e}")
        
        # Update Status
        db.update_sourcing_status(p_id, 'outreach_complete', found_inc=len(suppliers_found))
        print(f"Completed processing for {p_name}.")

if __name__ == "__main__":
    asyncio.run(run_enhanced_workflow())
