import sqlite3
import json
from run_email_campaign import format_email_body

DB_PATH = "rebusiness_automation.db"

def show_recent_sent_emails(limit=3):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get recently sent emails
    query = """
        SELECT 
            r.id,
            m.email,
            m.name as mfg_name,
            p.product_name,
            p.quantity,
            p.specifications,
            p.contract_id,
            s.title as sol_title,
            s.analysis_summary,
            s.data,
            s.url
        FROM manufacturer_requests r
        JOIN manufacturers m ON r.manufacturer_id = m.id
        JOIN products p ON r.product_id = p.id
        LEFT JOIN solicitations s ON p.contract_id = s.contract_id
        WHERE r.status = 'sent'
        ORDER BY r.id DESC
        LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    
    for row in rows:
        req_id, email, mfg_name, product_name, quantity, specs, contract_id, sol_title, analysis_summary, sol_data_json, sol_url = row
        
        print("=" * 80)
        print(f"EMAIL TO: {email} ({mfg_name})")
        print(f"PRODUCT: {product_name}")
        print("=" * 80)
        
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
        
        # Generate the email body using the same function
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
        
        print(f"\nSUBJECT: {subject}\n")
        print(body)
        print("\n" + "=" * 80 + "\n")
    
    conn.close()

if __name__ == "__main__":
    show_recent_sent_emails(3)
