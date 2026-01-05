import sqlite3
import json
import sys
import os

sys.path.append(os.getcwd())

from run_email_campaign import format_email_body

DB_PATH = "rebusiness_automation.db"

def preview_complete_solicitation():
    """Preview an email for a solicitation with PDF attachments."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get a solicitation with attachments
    query = """
        SELECT 
            p.id,
            p.product_name,
            p.quantity,
            p.specifications,
            p.contract_id,
            s.title,
            s.analysis_summary,
            s.data,
            s.url,
            COUNT(a.id) as attachment_count
        FROM products p
        JOIN solicitations s ON p.contract_id = s.contract_id
        INNER JOIN attachments a ON s.contract_id = a.contract_id
        WHERE s.contract_id = '197aaa46ad6c461db627c6934ba7fea4'
        ORDER BY s.contract_id
        LIMIT 1
    """
    
    cursor.execute(query)
    row = cursor.fetchone()
    
    if not row:
        print("No solicitations with attachments found.")
        return
    
    product_id, product_name, quantity, specs, contract_id, sol_title, analysis_summary, sol_data_json, sol_url, att_count = row
    
    print("=" * 80)
    print(f"PREVIEW EMAIL FOR COMPLETE SOLICITATION")
    print("=" * 80)
    print(f"Contract ID: {contract_id}")
    print(f"Product: {product_name}")
    print(f"Attachments: {att_count} PDF files")
    print("=" * 80)
    print()
    
    # Parse solicitation data
    delivery_loc_json = None
    timeline_str = None
    description_str = None
    due_date_str = None
    
    if sol_data_json:
        try:
            sdata = json.loads(sol_data_json)
            delivery_loc_json = json.dumps(sdata.get('delivery_location', {}))
            timeline_str = sdata.get('timeline')
            description_str = sdata.get('description')
            due_date_str = sdata.get('due_date')
        except: pass
    
    # Debug: Check extraction fields
    if sol_data_json:
        try:
            debug_data = json.loads(sol_data_json)
            print("\nDEBUG DATA EXTRACTION:")
            print(f"delivery_requirements: {json.dumps(debug_data.get('delivery_requirements'), indent=2)}")
            print(f"schedule_details: {debug_data.get('delivery_requirements', {}).get('schedule_details')}")
            print(f"primary_destination_address: {debug_data.get('delivery_requirements', {}).get('primary_destination_address')}")
            print("-" * 40)
        except Exception as e:
            print(f"DEBUG ERROR: {e}")

    # Generate the email
    print("DEBUG: Calling format_email_body now...")
    subject, body = format_email_body(
        contract_id,
        sol_title or "Solicitation",
        product_name,
        quantity,
        specs,
        delivery_loc_json,
        timeline_str,
        description_str,
        due_date_str,
        sol_url,
        sol_data_json
    )
    
    print(f"SUBJECT: {subject}\n")
    print(body)
    print("\n" + "=" * 80)
    
    conn.close()

if __name__ == "__main__":
    preview_complete_solicitation()
