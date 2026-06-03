import csv
import time
import datetime
import os
import logging
from ai_agents.OutreachAgent.email_service import EmailService

# --- Configuration (Hardcoded for this task as per discovery) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "bobbysmitty078@gmail.com"
SENDER_PASSWORD = "gwun semw qdwo ckxz" 

LEADS_FILE = "leads.csv"
RESULTS_FILE = "outreach_results.csv"
DELAY_BETWEEN_EMAILS = 2  # Seconds

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_deadline_date(days=7):
    future_date = datetime.date.today() + datetime.timedelta(days=days)
    return future_date.strftime("%B %d, %Y")

def format_email_body(row):
    """
    Formats the email body and subject using the template and row data.
    """
    solicitation_id = row.get("Solicitation ID", "N/A")
    product_keyword = row.get("Product Keyword", "Product")
    quantity = row.get("Quantity Needed", "See Solicitation")
    specs = row.get("Exact Size/Specs", "N/A")
    material = row.get("Material Composition", "N/A")
    
    # Clean up fields if they are None/Empty
    if not specs: specs = "As per standard specifications"
    if not material: material = "N/A"

    deadline = get_deadline_date()

    # --- Template Construction ---
    
    subject = f"Request for Quote - {solicitation_id} [{product_keyword}]"
    
    body = f"""Camp Sable, LLC
bobbysmitty078@gmail.com
{datetime.date.today().strftime("%B %d, %Y")}

Subject: {subject}

Dear Sales Department:

We are writing to request a formal quote for {product_keyword} matching specs: {specs}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement company.

Project Details:
Product/Service Required: {product_keyword}
Quantity Needed: {quantity}
Specifications/Requirements: {specs}. Material: {material}
Delivery Timeline: As per solicitation requirements
Delivery Location: As per solicitation requirements

Quote Requirements: Please include the following in your response:
Itemized pricing breakdown
Delivery schedule and shipping costs
Warranty information

Response Deadline: We require your quote to be submitted no later than {deadline} to ensure timely evaluation of all proposals.

If you have any questions regarding this request or need additional information, please contact me at bobbysmitty078@gmail.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

Sincerely,

John Campbell
Procurement Manager
Camp Sable, LLC
"""
    return subject, body

def main():
    print("--- Starting Outreach Automation ---")
    
    # 1. Initialize Email Service
    try:
        email_service = EmailService(SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD)
    except Exception as e:
        logger.error(f"Failed to initialize EmailService: {e}")
        return

    # 2. Read Leads
    if not os.path.exists(LEADS_FILE):
        logger.error(f"Leads file {LEADS_FILE} not found.")
        return

    leads = []
    with open(LEADS_FILE, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        leads = list(reader)

    print(f"Loaded {len(leads)} leads.")

    # 3. Process Leads
    results_header = ["Solicitation ID", "Product", "Lead Email", "Status", "Timestamp"]
    
    # Initialize results file with header if it doesn't exist
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(results_header)

    success_count = 0
    fail_count = 0

    for i, lead in enumerate(leads):
        email_addr = lead.get("Lead: Verified Email")
        if not email_addr or "@" not in email_addr:
            logger.warning(f"Skipping row {i+1}: Invalid email ({email_addr})")
            continue

        subject, body = format_email_body(lead)
        
        print(f"Sending to {email_addr} (Lead #{i+1})...", end="")
        
        try:
            success = email_service.send_email(email_addr, subject, body)
            status = "Sent" if success else "Failed"
            
            if success:
                print(" Success.")
                success_count += 1
            else:
                print(" Failed.")
                fail_count += 1
                
        except Exception as e:
            print(f" Error: {e}")
            status = f"Error: {e}"
            fail_count += 1

        # Log Result
        with open(RESULTS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                lead.get("Solicitation ID"),
                lead.get("Product Keyword"),
                email_addr,
                status,
                datetime.datetime.now().isoformat()
            ])

        time.sleep(DELAY_BETWEEN_EMAILS)

    print("\n--- Outreach Complete ---")
    print(f"Total Sent: {success_count}")
    print(f"Total Failed: {fail_count}")
    print(f"Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    main()
