import sqlite3
import json
import sys
import os

# Import the formatting functions from run_email_campaign
sys.path.append(os.getcwd())
from run_email_campaign import format_service_email_body, format_product_email_body

DB_PATH = "rebusiness_automation.db"
TARGET_IDS = [
    '04f3e1a2905844b994298c793f3ff78e',
    '197aaa46ad6c461db627c6934ba7fea4',
    '796b8188161049bfa359c2b16432e946',
    'cc36deeb238c4481888bee066b255901',
    'a1edf238787e4f4a83a87997bff9087e',
    '8e3c806a4472495fb936e1e2493f3304',
    'd4c90fd103a2402a88d306a6c4dce262',
    'e6fc48127e6041e5943291cf31192b7c'
]

def preview_leads():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    for cid in TARGET_IDS:
        cursor.execute("""
            SELECT contract_id, title, analysis_summary, url 
            FROM solicitations 
            WHERE contract_id = ?
        """, (cid,))
        sol = cursor.fetchone()
        
        if not sol:
            print(f"Skipping {cid} - Not found in DB.")
            continue
            
        # Get one product for this solicitation
        cursor.execute("SELECT product_name, quantity, specifications FROM products WHERE contract_id = ? LIMIT 1", (cid,))
        prod = cursor.fetchone()
        
        p_name = prod['product_name'] if prod else "General Service/Product"
        p_qty = prod['quantity'] if prod else "1"
        p_specs = prod['specifications'] if prod else ""
        
        data = {}
        try:
            data = json.loads(sol['analysis_summary'])
        except:
            print(f"Skipping {cid} - Invalid JSON.")
            continue
            
        cat = data.get('solicitation_category', 'Product')
        
        if cat == 'Service':
            print(f"\n[SERVICE PREVIEW] ID: {cid} | {sol['title']}")
            subject, plain, html = format_service_email_body(
                cid, sol['title'], p_name, p_qty, p_specs, 
                json.dumps(data.get('delivery_requirements', {}).get('primary_destination_address', 'Honolulu, HI')),
                data.get('delivery_requirements', {}).get('schedule_details'),
                data.get('summary'),
                data.get('quotes_due_date'),
                sol['url'],
                sol['analysis_summary']
            )
        else:
            print(f"\n[PRODUCT PREVIEW] ID: {cid} | {sol['title']}")
            subject, plain, html = format_product_email_body(
                cid, sol['title'], p_name, p_qty, p_specs,
                json.dumps(data.get('delivery_requirements', {}).get('primary_destination_address', 'Honolulu, HI')),
                data.get('delivery_requirements', {}).get('schedule_details'),
                data.get('summary'),
                data.get('quotes_due_date'),
                sol['url'],
                sol['analysis_summary']
            )
            
        print("-" * 80)
        print(f"SUBJECT: {subject}")
        print("-" * 40)
        print(plain)
        print("-" * 80)

    conn.close()

if __name__ == "__main__":
    preview_leads()
