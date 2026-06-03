import sqlite3
import json
import sys
import os

sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'ai_agents/OutreachAgent'))

from run_email_campaign import format_service_email_body, format_product_email_body
from email_service import EmailService
from config import SMTP_CONFIG

# Configuration
TEST_EMAIL = "tanzeelrrehman913@gmail.com"
DB_PATH = "rebusiness_automation.db"
LEADS = [
    {"id": "04f3e1a2905844b994298c793f3ff78e", "type": "Service"}, # JB-MDL
    {"id": "e6fc48127e6041e5943291cf31192b7c", "type": "Product"}  # RO Systems
]

def send_2_test_emails():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Using credentials found in OutreachAgent test block for immediate testing
    try:
        service = EmailService(
            "smtp.gmail.com", 
            587, 
            "bobbysmitty078@gmail.com", 
            "gwun semw qdwo ckxz"
        )
    except Exception as e:
        print(f"Failed to initialize EmailService: {e}")
        return

    for lead in LEADS:
        print(f"\n--- Processing Lead: {lead['id']} ({lead['type']}) ---")
        cursor.execute("SELECT contract_id, title, analysis_summary, url FROM solicitations WHERE contract_id = ?", (lead['id'],))
        sol = cursor.fetchone()
        if not sol:
            print(f"Error: Lead {lead['id']} not found.")
            continue

        cursor.execute("SELECT product_name, quantity, specifications FROM products WHERE contract_id = ? LIMIT 1", (lead['id'],))
        prod = cursor.fetchone()
        
        p_name = prod['product_name'] if prod else "Professional Services"
        p_qty = prod['quantity'] if prod else "1"
        p_specs = prod['specifications'] if prod else ""
        
        data = json.loads(sol['analysis_summary'])
        
        if lead['type'] == 'Service':
            subject, plain, html = format_service_email_body(
                lead['id'], sol['title'], p_name, p_qty, p_specs, 
                json.dumps(data.get('delivery_requirements', {}).get('primary_destination_address', 'See Solicitation')),
                data.get('delivery_requirements', {}).get('schedule_details'),
                data.get('summary'),
                data.get('quotes_due_date'),
                sol['url'],
                sol['analysis_summary']
            )
        else:
            subject, plain, html = format_product_email_body(
                lead['id'], sol['title'], p_name, p_qty, p_specs,
                json.dumps(data.get('delivery_requirements', {}).get('primary_destination_address', 'See Solicitation')),
                data.get('delivery_requirements', {}).get('schedule_details'),
                data.get('summary'),
                data.get('quotes_due_date'),
                sol['url'],
                sol['analysis_summary']
            )
        
        print(f"Sending to {TEST_EMAIL}...")
        success = service.send_email(
            to_email=TEST_EMAIL,
            subject=f"[TEST] {subject}",
            body=plain,
            html_body=html
        )
        if success:
            print(f"Lead {lead['id']} sent successfully!")
        else:
            print(f"Failed to send Lead {lead['id']}.")

    conn.close()

if __name__ == "__main__":
    send_2_test_emails()
