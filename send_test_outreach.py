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
TARGET_CID = "04f3e1a2905844b994298c793f3ff78e" # JB-MDL Service Lead

def send_test_email():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Fetch real data
    cursor.execute("SELECT contract_id, title, analysis_summary, url FROM solicitations WHERE contract_id = ?", (TARGET_CID,))
    sol = cursor.fetchone()
    if not sol:
        print(f"Error: Lead {TARGET_CID} not found in database.")
        return

    cursor.execute("SELECT product_name, quantity, specifications FROM products WHERE contract_id = ? LIMIT 1", (TARGET_CID,))
    prod = cursor.fetchone()
    
    p_name = prod['product_name'] if prod else "Professional Services"
    p_qty = prod['quantity'] if prod else "1"
    p_specs = prod['specifications'] if prod else ""
    
    data = json.loads(sol['analysis_summary'])
    cat = data.get('solicitation_category', 'Service')
    
    # 2. Format body using finalized templates
    if cat == 'Service':
        subject, plain, html = format_service_email_body(
            TARGET_CID, sol['title'], p_name, p_qty, p_specs, 
            json.dumps(data.get('delivery_requirements', {}).get('primary_destination_address', 'See Solicitation')),
            data.get('delivery_requirements', {}).get('schedule_details'),
            data.get('summary'),
            data.get('quotes_due_date'),
            sol['url'],
            sol['analysis_summary']
        )
    else:
        subject, plain, html = format_product_email_body(
            TARGET_CID, sol['title'], p_name, p_qty, p_specs,
            json.dumps(data.get('delivery_requirements', {}).get('primary_destination_address', 'See Solicitation')),
            data.get('delivery_requirements', {}).get('schedule_details'),
            data.get('summary'),
            data.get('quotes_due_date'),
            sol['url'],
            sol['analysis_summary']
        )
    
    # 3. Send test email
    print(f"Sending test email to {TEST_EMAIL}...")
    try:
        service = EmailService(
            SMTP_CONFIG['smtp_server'], 
            SMTP_CONFIG['smtp_port'], 
            SMTP_CONFIG['smtp_username'], 
            SMTP_CONFIG['smtp_password']
        )
        success = service.send_email(
            to_email=TEST_EMAIL,
            subject=f"[TEST] {subject}",
            body=plain,
            html_body=html
        )
        if success:
            print("Test email sent successfully!")
        else:
            print("Failed to send email (Service returned false).")
    except Exception as e:
        print(f"Failed to send email: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    send_test_email()
