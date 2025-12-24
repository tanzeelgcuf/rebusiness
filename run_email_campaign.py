import sqlite3
import time
import datetime
import logging
import sys
import os
import json

# Add ai_agents path
sys.path.append(os.path.abspath('ai_agents'))

from ai_agents.OutreachAgent.email_service import EmailService

# --- Configuration ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "john@campsable.com"
SENDER_PASSWORD = "gwun semw qdwo ckxz" 

DB_PATH = "rebusiness_automation.db"
DELAY_BETWEEN_EMAILS = 5 # Seconds

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_deadline_date(days=7):
    future_date = datetime.date.today() + datetime.timedelta(days=days)
    return future_date.strftime("%B %d, %Y")


def format_email_body(solicitation_id, solicitation_title, product_name, quantity, specs, delivery_location_json, timeline=None, description=None, due_date_str=None):
    """
    Formats the email body and subject using the updated User Template.
    """
    # 1. Parse Delivery Location
    delivery_loc_str = "As per solicitation requirements"
    try:
        if delivery_location_json:
            loc_data = json.loads(delivery_location_json)
            # Extracted format: {street, city, state, zip_code}
            if isinstance(loc_data, dict):
                parts = [loc_data.get(k) for k in ['street', 'city', 'state', 'zip_code'] if loc_data.get(k)]
                if parts:
                    delivery_loc_str = ", ".join(parts)
    except:
        pass # Fallback

    # 2. Clean up fields
    if not specs: specs = "As per standard specifications"
    if not quantity: quantity = "See Solicitation"
    if not timeline: timeline = "As per solicitation requirements"
    if not description: description = "As per solicitation"
    
    # 3. Calculate Deadline
    # User requested: "4 days prior to the date due listed on the solicitation"
    deadline_str = get_deadline_date(days=7) # Default
    
    if due_date_str:
        try:
            # Parse YYYY-MM-DD
            due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d").date()
            # Subtract 4 days
            request_deadline = due_date - datetime.timedelta(days=4)
            
            # Sanity Check: If deadline is in the past, or too strict (e.g. today), handle gracefully?
            # User said: "usually 4 days prior". We will strictly follow this.
            deadline_str = request_deadline.strftime("%B %d, %Y")
        except:
             pass # Stick to default

    today_str = datetime.date.today().strftime("%B %d, %Y")

    # --- Template Construction (USER PROVIDED FORMAT) ---
    
    subject = f"Request for Quote -Subject line in email to include notice ID number {solicitation_id} [{product_name}]"
    
    body = f"""Camp Sable, LLC
john@campsable.com
{today_str}

Subject: Request for Quote - Subject line in email to include notice ID number {solicitation_id} [{product_name}]

Dear Sales Department:

We are writing to request a formal quote for {description}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement company.

Project Details:
Product/Service Required: {product_name}
Quantity Needed: {quantity}
Specifications/Requirements: {specs}
Delivery Timeline: {timeline}
Delivery Location: {delivery_loc_str}

Quote Requirements: Please include the following in your response:
Itemized pricing breakdown
Delivery schedule and shipping costs
Warranty information

Response Deadline: We require your quote to be submitted no later than {deadline_str} to ensure timely evaluation of all proposals.

If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

Sincerely,

John Campbell
Procurement Manager
Camp Sable, LLC
"""
    return subject, body

def run_campaign(limit=50):
    logger.info("--- Starting Direct Email Campaign ---")
    
    # 1. Initialize Email Service
    try:
        email_service = EmailService(SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD)
    except Exception as e:
        logger.error(f"Failed to initialize EmailService: {e}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. Find Pending Requests
    # Join with solicitations to get analysis_summary (for delivery location)
    query = """
        SELECT 
            r.id, 
            m.email, 
            p.product_name, 
            p.quantity, 
            p.specifications, 
            p.contract_id,
            m.name as mfg_name,
            s.title as sol_title,
            s.analysis_summary,
            s.data
        FROM manufacturer_requests r
        JOIN manufacturers m ON r.manufacturer_id = m.id
        JOIN products p ON r.product_id = p.id
        LEFT JOIN solicitations s ON p.contract_id = s.contract_id
        WHERE (r.status = 'pending' OR r.status = 'failed')
          AND m.email IS NOT NULL 
          AND m.email != ''
        LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    tasks = cursor.fetchall()
    
    if not tasks:
        logger.info("No pending tasks found with valid manufacturer emails.")
        conn.close()
        return 0

    logger.info(f"Found {len(tasks)} actionable tasks.")

    success_count = 0
    fail_count = 0

    for i, task in enumerate(tasks):
        req_id, email_addr, product_name, quantity, specs, contract_id, mfg_name, sol_title, analysis_json, sol_data_json = task
        
        # Parse analysis to get exact delivery location dictionary if possible
        delivery_loc_json = None
        timeline_str = None
        description_str = None
        
        if analysis_json:
             try:
                 data = json.loads(analysis_json)
                 if data.get('delivery_location'):
                     delivery_loc_json = json.dumps(data.get('delivery_location'))
                 if data.get('delivery_timeline'):
                      timeline_str = data.get('delivery_timeline')
                 # Try to get description
                 # simplified logic for straight run_campaign (enrich_and_send has more specific logic)
                 if data.get('summary'): description_str = data.get('summary')
             except: pass
        
        # Parse sol_data to get due_date
        due_date_str = None
        if sol_data_json:
            try:
                sdata = json.loads(sol_data_json)
                due_date_str = sdata.get('due_date')
            except: pass


        # --- VALIDATION START ---
        # 1. Validate Email Address (Strict)
        clean_email = email_addr.lower().strip()
        invalid_extensions = ['.avif', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp']
        invalid_domains = ['sentry.wixpress.com', 'wixpress.com', 'sentry.io']
        
        if clean_email.endswith('.'):
             cursor.execute("UPDATE manufacturer_requests SET status = 'failed', notes = 'Invalid Email Format (Trailing Dot)' WHERE id = ?", (req_id,))
             conn.commit()
             logger.warning(f"Skipping invalid email (trailing dot): {email_addr}")
             fail_count += 1
             continue
        
        if any(clean_email.endswith(ext) for ext in invalid_extensions) or \
           any(domain in clean_email for domain in invalid_domains) or \
           "@" not in clean_email or "." not in clean_email.split("@")[-1]:
            logger.warning(f"Skipping invalid email: {email_addr}")
            cursor.execute("UPDATE manufacturer_requests SET status = 'failed', notes = 'Invalid Email Format' WHERE id = ?", (req_id,))
            conn.commit()
            fail_count += 1
            continue

        # 2. Validate Product Data Quality
        # If specs are "N/A" or very short, and description is missing, it's a low quality request.
        # User feedback: "still our system is missing key information... missing Spcifications... N/A"
        # Logic: If specs are empty/N/A, try to fallback to Description. If both bad, SKIP.
        
        real_specs = specs
        if not real_specs or len(real_specs) < 5 or real_specs in ["As per standard specifications", "N/A", "None"]:
             # Try to fetch description from DB to augment? 
             # For now, if we don't have good specs, we mark as 'flagged_data_missing' and skip sending.
             cursor.execute("UPDATE manufacturer_requests SET status = 'failed', notes = 'Missing Specs/Qty - Quality Control' WHERE id = ?", (req_id,))
             conn.commit()
             logger.warning(f"Skipping {mfg_name}: Missing key product information (Specs: {specs})")
             fail_count += 1
             continue
        # --- VALIDATION END ---

        # Handle missing solicitation data (Left Join)
        display_id = contract_id
        display_title = sol_title if sol_title else f"Solicitation {contract_id}"
        
        subject, body = format_email_body(display_id, display_title, product_name, quantity, real_specs, delivery_loc_json, timeline_str, description_str, due_date_str)
        
        try:
            success = email_service.send_email(email_addr, subject, body)
            
            if success:
                cursor.execute("""
                    UPDATE manufacturer_requests 
                    SET status = 'sent', response_date = CURRENT_TIMESTAMP, method = 'email', notes = 'Direct Email Campaign Used' 
                    WHERE id = ?
                """, (req_id,))
                conn.commit()
                logger.info("  Success.")
                success_count += 1
            else:
                cursor.execute("UPDATE manufacturer_requests SET status = 'failed', notes = 'SMTP Error' WHERE id = ?", (req_id,))
                conn.commit()
                logger.warning("  Failed to send.")
                fail_count += 1
                
        except Exception as e:
            logger.error(f"  Error: {e}")
            cursor.execute("UPDATE manufacturer_requests SET status = 'failed', notes = ? WHERE id = ?", (str(e), req_id))
            conn.commit()
            fail_count += 1

        time.sleep(DELAY_BETWEEN_EMAILS)

    conn.close()
    logger.info(f"--- Campaign Complete. Sent: {success_count}, Failed: {fail_count} ---")
    return len(tasks)

if __name__ == "__main__":
    limit = 50
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except: pass
    run_campaign(limit)
