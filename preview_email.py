import sqlite3
import json
import sys
import os

# Ensure we can import from current directory
sys.path.append(os.getcwd())

from run_email_campaign import format_email_body
from ai_agents.DeepSpecAgent.deep_spec_agent import DeepSpecAgent

DB_PATH = "rebusiness_automation.db"

def preview_sample_email():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # query for a product that has specs and valid details to show a good sample
    query = """
        SELECT 
            p.contract_id,
            s.title,
            p.product_name,
            p.quantity,
            p.specifications,
            s.analysis_summary,
            s.data,
            s.url,
            p.id as product_id
        FROM products p
        LEFT JOIN solicitations s ON p.contract_id = s.contract_id
        WHERE p.contract_id IN ('617589ba51', '9d653ba6cb', 'ab8b2b3639', '5189753458', '04f3e1a2905844b994298c793f3ff78e', '197aaa46ad6c461db627c6934ba7fea4')
        ORDER BY p.contract_id DESC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("No suitable products found for preview.")
        return

    for row in rows:
        contract_id, sol_title, product_name, quantity, specs, analysis_json, sol_data_json, sol_url, product_id = row
        
        real_specs = specs
        delivery_loc_json = None
        timeline_str = None
        description_str = None
        due_date_str = None
        real_specs = specs
        if analysis_json:
            try:
                data = json.loads(analysis_json)
                if data.get('delivery_location'):
                    delivery_loc_json = json.dumps(data.get('delivery_location'))
                if data.get('delivery_timeline'):
                    timeline_str = data.get('delivery_timeline')
                
                # Match run_email_campaign logic
                p_details = data.get('product_details', [])
                if p_details and isinstance(p_details, list):
                    extracted_specs = []
                    total_qty = 0
                    descriptions = []
                    
                    for item in p_details:
                        combined_item_info = []
                        if item.get('specifications'):
                            combined_item_info.extend(item.get('specifications'))
                        if item.get('description') and len(item.get('description')) > 10:
                            combined_item_info.append(item.get('description'))
                        
                        if combined_item_info:
                            extracted_specs.append(" | ".join(combined_item_info))
                        
                        try:
                            q = item.get('quantity')
                            if q: total_qty += float(str(q).replace(',','').split()[0])
                        except: pass
                        
                        if item.get('description'):
                            descriptions.append(item.get('description'))
                    
                    if extracted_specs:
                        real_specs = "; ".join(extracted_specs)
                    
                    if total_qty > 0:
                        quantity = str(int(total_qty)) if total_qty.is_integer() else str(total_qty)
                        if p_details[0].get('unit'): quantity += f" {p_details[0].get('unit')}"
                    
                    if descriptions:
                        description_str = "; ".join(descriptions[:3])
                
                if not description_str and data.get('summary'):
                     description_str = data.get('summary')

                # Deep Extraction of Real Notice ID from 'data' field
                if sol_data_json:
                    try:
                        sdata = json.loads(sol_data_json)
                        real_notice_id = sdata.get('Notice ID') or sdata.get('notice_id')
                        
                        # Fallback: Look inside description text if it's there
                        if not real_notice_id and sdata.get('description'):
                            import re
                            match = re.search(r"Notice ID\s*[\n\r]*\s*([A-Za-z0-9\-]+)", sdata.get('description'))
                            if match:
                                real_notice_id = match.group(1)
                                
                        if real_notice_id and len(real_notice_id) > 5:
                            contract_id = real_notice_id # Override display ID with Real ID
                    except: pass
            except: pass
        
        # Match run_email_campaign logic for Deep Spec Enrichment
        if product_id and (not real_specs or "DEEP SPECS" not in real_specs):
            import re
            nsn_match = re.search(r"(\d{4}-\d{2}-\d{3}-\d{4}|\d{13})", real_specs or "")
            if nsn_match:
                spec_agent = DeepSpecAgent()
                # Run research (don't necessarily update DB in preview mode, or do we?)
                # Actually, enrichment updates DB. Let's do it so the data is saved.
                if spec_agent.enrich_product_specs(product_id):
                    # Fetch enriched specs
                    s_conn = sqlite3.connect(DB_PATH)
                    s_cursor = s_conn.cursor()
                    s_cursor.execute("SELECT specifications FROM products WHERE id = ?", (product_id,))
                    updated_row = s_cursor.fetchone()
                    if updated_row:
                        real_specs = updated_row[0]
                    s_conn.close()

        # Failsafe for specs
        if not real_specs or len(real_specs) < 15 or real_specs in ["As per standard specifications", "N/A", "None", "See Solicitation"]:
             if description_str and len(description_str) > 20:
                 real_specs = description_str
        
        # FAILSAFE 2: If we have "Drawings not available" text, we MUST append the product name
        if "Drawings or technical data are not available" in (real_specs or ""):
             if analysis_json:
                 try:
                     a_data = json.loads(analysis_json)
                     p_names = [p.get('name') for p in a_data.get('product_details', []) if p.get('name')]
                     if p_names:
                         context_str = f"Specific Items requested: {', '.join(p_names)}"
                         real_specs = f"{real_specs} | {context_str}"
                 except: pass

        if sol_data_json:
            try:
                sdata = json.loads(sol_data_json)
                due_date_str = sdata.get('due_date')
            except: pass

        # Generate Preview
        display_id = contract_id
        display_title = sol_title if sol_title else f"Solicitation {contract_id}"
        
        subject, body, html_body = format_email_body(
            display_id, 
            display_title, 
            product_name, # concise for subject
            quantity, 
            real_specs, # enriched specs
            delivery_loc_json, 
            timeline_str, 
            description_str, 
            due_date_str,
            sol_url,
            analysis_json
        )
        
        print("-" * 60)
        print("EMAIL PREVIEW")
        print("-" * 60)
        print(f"To: [Supplier Email]")
        print(f"Subject: {subject}")
        print("-" * 20)
        print(body)
        print("-" * 60)


if __name__ == "__main__":
    preview_sample_email()
