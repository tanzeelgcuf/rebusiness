import time
import sys
import logging
import sqlite3
import json
from run_email_campaign import run_campaign, DB_PATH, format_email_body, SENDER_EMAIL, SENDER_PASSWORD, SMTP_SERVER, SMTP_PORT
from data_enrichment import DataEnricher
from ai_agents.OutreachAgent.email_service import EmailService

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EnrichAndSend")

def run_smart_campaign(batch_size=10):
    logger.info("--- Starting SMART Email Campaign (Enrichment Enabled) ---")
    
    enricher = DataEnricher()
    email_service = EmailService(SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Fetch Pending Requests (Using the new LEFT JOIN logic from run_email_campaign)
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
            s.url,
            s.data
        FROM manufacturer_requests r
        JOIN manufacturers m ON r.manufacturer_id = m.id
        JOIN products p ON r.product_id = p.id
        LEFT JOIN solicitations s ON p.contract_id = s.contract_id
        WHERE r.status = 'pending'
          AND m.email IS NOT NULL AND m.email != ''
        LIMIT ?
    """
    
    cursor.execute(query, (batch_size,))
    tasks = cursor.fetchall()
    
    if not tasks:
        logger.info("No pending tasks.")
        conn.close()
        return 0
        
    for i, task in enumerate(tasks):
        req_id, email_addr, product_name, quantity, specs, contract_id, mfg_name, sol_title, analysis_json, sol_url, sol_data_json = task
        
        logger.info(f"[{i+1}/{len(tasks)}] Processing {mfg_name} for {product_name}...")
        
        # --- QUALITY CHECK ---
        # 1. Check Quantity (Must be numeric and > 0)
        has_qty = False
        try:
            if quantity and float(str(quantity).strip()) > 0:
                has_qty = True
        except:
            pass
            
        # 2. Check Delivery Location
        has_loc = False
        if analysis_json:
            try:
                data = json.loads(analysis_json)
                if data.get('delivery_location'):
                    has_loc = True
            except: pass

        # 3. Check Content Density (NEW: Fix "Lacking Description" issue)
        # If specs are too short (< 20 chars) or generic, OR product name is vague and we lack description.
        weak_specs = not specs or len(str(specs)) < 20 or str(specs).lower() in ['n/a', 'none', 'see solicitation']
        
        needs_enrichment = not has_qty or not has_loc or weak_specs
        
        if needs_enrichment:
            logger.info(f"  > Data quality weak (Qty: {has_qty}, Loc: {has_loc}, Weak Specs: {weak_specs}). Triggering Enrichment...")
            
            # If URL is missing from LEFT JOIN, we can't fetch. 
            # Try to find URL from standard URL pattern if missing? Or just skip deep fetch.
            if not sol_url:
                sol_url = f"https://sam.gov/search/?index=opp&page=1&sort=-modifiedDate&pageSize=25&sfm%5BsimpleSearch%5D%5BkeywordRadio%5D=ALL&sfm%5BsimpleSearch%5D%5BkeywordTags%5D={contract_id}"

            updated_analysis = enricher.enrich_contract(contract_id, sol_url)
            
            if updated_analysis:
                # Refresh Data from Analysis
                logger.info("  > Enrichment Successful. Refreshing data...")
                
                # Check for new qty
                new_products = updated_analysis.get('product_details', [])
                for np in new_products:
                    if np.get('name') == product_name or len(new_products) == 1:
                        if np.get('quantity'): quantity = np.get('quantity')
                        if np.get('specifications'): specs = "; ".join(np.get('specifications')) if isinstance(np.get('specifications'), list) else np.get('specifications')
                        break
                
                # Check for new Loc
                if updated_analysis.get('delivery_location'):
                    analysis_json = json.dumps(updated_analysis)
            else:
                # Enrichment Failed (e.g. invalid Contract ID like SAM-CNLES)
                # DO NOT SEND BAD DATA.
                logger.warning(f"  > Enrichment FAILED for {contract_id}. Marking as failed to prevent bad email.")
                cursor.execute("UPDATE manufacturer_requests SET status = 'failed', notes = 'Enrichment Failed - Invalid Solicitation' WHERE id = ?", (req_id,))
                conn.commit()
                continue # Skip to next task

        # Re-parse location AND timeline from (potentially updated) analysis_json
        
        # Re-parse location AND timeline from (potentially updated) analysis_json
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
                
                # Try to get product description first
                # The analysis JSON has 'product_details' list.
                # We need to find the matching product description.
                products_list = data.get('product_details', [])
                for p in products_list:
                    if p.get('name') == product_name:
                        description_str = p.get('description')
                        break
                
                # Fallback to summary if no product description
                if not description_str:
                    description_str = data.get('summary')
                    
            except: pass
            
        display_title = sol_title if sol_title else f"Solicitation {contract_id}"
        
        # Validation Logic (Duplicated from run_email_campaign to be safe)
        clean_email = email_addr.lower().strip()
        invalid_domains = ['sentry.wixpress.com', 'wixpress.com', 'sentry.io']
        if clean_email.endswith('.') or any(d in clean_email for d in invalid_domains):
             logger.warning("Skipping invalid email.")
             cursor.execute("UPDATE manufacturer_requests SET status = 'failed', notes = 'Invalid Email' WHERE id = ?", (req_id,))
             conn.commit()
             continue

        # Extract Due Date
        due_date_str = None
        if sol_data_json:
            try:
                sdata = json.loads(sol_data_json)
                due_date_str = sdata.get('due_date')
            except: pass

        subject, body = format_email_body(contract_id, display_title, product_name, quantity, specs, delivery_loc_json, timeline_str, description_str, due_date_str)
        
        try:
            success = email_service.send_email(email_addr, subject, body)
            if success:
                cursor.execute("UPDATE manufacturer_requests SET status = 'sent', response_date = CURRENT_TIMESTAMP, method = 'email', notes = 'Enriched Smart Send' WHERE id = ?", (req_id,))
                logger.info("  Email Sent.")
            else:
                cursor.execute("UPDATE manufacturer_requests SET status = 'failed', notes = 'SMTP Fail' WHERE id = ?", (req_id,))
                logger.warning("  SMTP Failed.")
        except Exception as e:
            logger.error(f"  Send Error: {e}")
            cursor.execute("UPDATE manufacturer_requests SET status = 'failed', notes = ? WHERE id = ?", (str(e), req_id))
            
        conn.commit()
        time.sleep(5) # Polite delay

    conn.close()
    enricher.close()
    return len(tasks)

if __name__ == "__main__":
    while True:
        try:
            count = run_smart_campaign(5) # Smaller batch for enrichment
            if count == 0:
                break
            time.sleep(10)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Loop Crash: {e}")
            time.sleep(30)
