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
from ai_agents.DeepSpecAgent.deep_spec_agent import DeepSpecAgent

# --- Configuration ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "bobbysmitty078@gmail.com"
SENDER_PASSWORD = "gwun semw qdwo ckxz" 

DB_PATH = "rebusiness_automation.db"
DELAY_BETWEEN_EMAILS = 5 # Seconds

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_deadline_date(days=7):
    future_date = datetime.date.today() + datetime.timedelta(days=days)
    return future_date.strftime("%B %d, %Y")

def get_business_days_prior(base_date, days):
    """
    Subtracts n business days from base_date, skipping weekends.
    """
    if isinstance(base_date, str):
        try:
            # Handle various date formats
            for fmt in ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"]:
                try:
                    base_date = datetime.datetime.strptime(base_date, fmt).date()
                    break
                except: continue
            if isinstance(base_date, str): return base_date # Failed to parse
        except: return base_date

    current_date = base_date
    while days > 0:
        current_date -= datetime.timedelta(days=1)
        if current_date.weekday() < 5: # Monday-Friday
            days -= 1
    return current_date.strftime("%B %d, %Y")


def calculate_internal_deadline(due_date_str):
    """Calculates internal deadline (4 business days prior)."""
    if not due_date_str or "Information not provided" in due_date_str:
        return due_date_str
    
    # Try to extract just the date part if there's time info
    date_part = due_date_str.split(' at ')[0].split(' ET')[0].split(' PT')[0].strip()
    return get_business_days_prior(date_part, 4)


def clean_val(val, default):
    if not val: return default
    s = str(val).strip().upper()
    placeholders = [
        "NOT_FOUND", "NONE", "NULL", "{}", "[]", "SEE SOLICITATION", 
        "INFORMATION NOT AVAILABLE", "SEE SOLICITATION DOCUMENTS FOR DETAILS", 
        "NOT SPECIFIED", "TO BE DETERMINED", "TBD", "REFER TO SOW", 
        "INFORMATION NOT PROVIDED IN SOLICITATION"
    ]
    if s in placeholders or any(p in s for p in ["SEE SOLICITATION", "NOT PROVIDED"]):
        return default
    return val

def format_service_email_body(sol_id, sol_title, product_name, quantity, specs, delivery_loc_json, timeline=None, description=None, due_date_str=None, sol_url=None, analysis_json=None):
    """
    Formats the email body for SERVICE solicitations matching Claude Services List.odt format exactly.
    Returns: subject, plain_body, html_body
    """
    today_str = datetime.date.today().strftime("%B %d, %Y")
    missing_msg = "Information not provided in solicitation"
    
    # Parse Analysis Data
    data = {}
    if analysis_json:
        try:
            data = json.loads(analysis_json)
        except: pass

    # Extract key fields
    notice_id = data.get('notice_id') or data.get('contract_id') or sol_id
    real_title = data.get('title') or sol_title
    quotes_due = due_date_str or clean_val(data.get('quotes_due_date'), missing_msg)
    internal_deadline = calculate_internal_deadline(quotes_due)
    
    # --- SUBJECT ---
    subject = f"Request for Quote - {real_title} ({notice_id})"
    
    # --- SECTION 1: HEADER & INTRO ---
    intro_text = f"""Dear Vendor,

We are writing to request a formal quote for {product_name}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

If you have any questions regarding this request or need additional information, please contact me at {SENDER_EMAIL}. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

[Contracting Team]"""

    intro_html = f"""<p>Dear Vendor,</p>
<p>We are writing to request a formal quote for {product_name}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.</p>
<p>If you have any questions regarding this request or need additional information, please contact me at {SENDER_EMAIL}. We look forward to establishing a mutually beneficial business relationship.</p>
<p>Thank you for your time and consideration.</p>
<p>[Contracting Team]</p>"""

    # --- SECTION 2: General Overview ---
    agency_name = data.get('soliciting_entity') or "U.S. Army Corps of Engineers (USACE)"
    delivery_period = clean_val(data.get('delivery_requirements', {}).get('schedule_aro'), "3 years (approx)")
    location = clean_val(data.get('project_scope', {}).get('work_site_list', []), missing_msg)
    if isinstance(location, list) and location:
        location = ", ".join([loc.get('site_name', '') for loc in location if loc.get('site_name')])
    contract_type = clean_val(data.get('contract_type'), "Firm Fixed Price")
    set_aside = clean_val(data.get('set_aside_type'), "100% Small Business Set-Aside")
    
    overview_text = f"""🔹 General Overview
Project Name: {real_title}
Solicitation Number: {notice_id}
Agency: {agency_name}
Delivery Period: {delivery_period}
Location: {location}
Type: {contract_type}
Set-Aside: {set_aside}"""

    overview_html = f"""<h3>🔹 General Overview</h3>
<ul>
<li><b>Project Name:</b> {real_title}</li>
<li><b>Solicitation Number:</b> {notice_id}</li>
<li><b>Agency:</b> {agency_name}</li>
<li><b>Delivery Period:</b> {delivery_period}</li>
<li><b>Location:</b> {location}</li>
<li><b>Type:</b> {contract_type}</li>
<li><b>Set-Aside:</b> {set_aside}</li>
</ul>"""

    # --- SECTION 3: Scope of Work ---
    scope_data = data.get('project_scope', {})
    task_desc = scope_data.get('task_descriptions', [])
    scope_bullets = ""
    scope_html_bullets = ""
    if task_desc:
        for t in task_desc[:5]:
            desc = t.get('task') or t.get('requirement') or ""
            if desc:
                scope_bullets += f"   • {desc}\n"
                scope_html_bullets += f"<li>{desc}</li>"
    else:
        scope_bullets = f"   • {product_name} services as per solicitation specifications.\n"
        scope_html_bullets = f"<li>{product_name} services as per solicitation specifications.</li>"

    scope_text = f"🔹 Scope of Work\n{scope_bullets}"
    scope_html = f"<h3>🔹 Scope of Work</h3><ul>{scope_html_bullets}</ul>"

    # --- SECTION 4: Key Requirements ---
    comp = data.get('compliance', {})
    security = clean_val(comp.get('security_clearance_needed'), "Standard DoD/Army training and vetting required.")
    wages = clean_val(data.get('wage_rates'), "Service Contract Act (SCA) wage determinations apply.")
    insurance = clean_val(data.get('insurance_limits'), "$1M General Liability per occurrence.")
    
    key_reqs_text = f"""🔹 Key Requirements
Security / Compliance: {security}
Wage & Labor Compliance: {wages}
Insurance Requirements: {insurance}
Veteran Hiring Encouraged: Strongly urged to employ U.S. veterans and use related resources."""

    key_reqs_html = f"""<h3>🔹 Key Requirements</h3>
<ul>
<li><b>Security / Compliance:</b> {security}</li>
<li><b>Wage & Labor Compliance:</b> {wages}</li>
<li><b>Insurance Requirements:</b> {insurance}</li>
<li><b>Veteran Hiring Encouraged:</b> Strongly urged to employ U.S. veterans and use related resources.</li>
</ul>"""

    # --- SECTION 5: Contract Clauses / Legal ---
    legal_text = f"""🔹 Contract Clauses / Legal
Includes FAR and DFARS clauses on small business utilization, subcontracting limits, ethics, payment, security, and EEO.
Limitations on Subcontracting: Prime must perform at least 50% of the service cost.
Prohibited Technologies: No use of Kaspersky, Huawei, ZTE, or ByteDance (TikTok) software/equipment."""

    legal_html = f"""<h3>🔹 Contract Clauses / Legal</h3>
<p>Includes FAR and DFARS clauses on small business utilization, subcontracting limits, ethics, payment, security, and EEO.</p>
<ul>
<li><b>Limitations on Subcontracting:</b> Prime must perform at least 50% of the service cost.</li>
<li><b>Prohibited Technologies:</b> No use of Kaspersky, Huawei, ZTE, or ByteDance (TikTok) software/equipment.</li>
</ul>"""

    # --- SECTION 6: Bid Submission Instructions ---
    sub_instr = data.get('submission_instructions', {})
    method = sub_instr.get('method', 'Email/Portal per solicitation')
    checklist = data.get('submission_checklist', [])
    checklist_str = "\n".join([f"   • {c}" for c in checklist])
    checklist_html = "".join([f"<li>{c}</li>" for c in checklist])
    
    submission_text = f"""🔹 Bid Submission Instructions
Due Date: {quotes_due}
Bid Delivery Options: {method}
Required with Bid:
{checklist_str}"""

    submission_html = f"""<h3>🔹 Bid Submission Instructions</h3>
<ul>
<li><b>Due Date:</b> {quotes_due}</li>
<li><b>Bid Delivery Options:</b> {method}</li>
<li><b>Required with Bid:</b><ul>{checklist_html}</ul></li>
</ul>"""

    # --- SECTION 7: Post-Award Responsibilities ---
    post_award_text = f"""🔹 Post-Award Responsibilities
Maintain training, vetting, insurance, and payroll documentation.
Submit invoices electronically via approved agency portal.
Maintain SAM registration throughout contract performance."""

    post_award_html = f"""<h3>🔹 Post-Award Responsibilities</h3>
<ul>
<li>Maintain training, vetting, insurance, and payroll documentation.</li>
<li>Submit invoices electronically via approved agency portal.</li>
<li>Maintain SAM registration throughout contract performance.</li>
</ul>"""

    # --- SECTION 8: Important Contacts & Reference Info ---
    ref_info_text = f"""🔹 Important Contacts & Reference Info
Contracting Officer: Refer to solicitation documents
Reference Websites: SAM.gov – Registration & solicitations"""

    ref_info_html = f"""<h3>🔹 Important Contacts & Reference Info</h3>
<ul>
<li><b>Contracting Officer:</b> Refer to solicitation documents</li>
<li><b>Reference Websites:</b> SAM.gov – Registration & solicitations</li>
</ul>"""

    # --- SECTION 9: Overall Project Summary ---
    summary = data.get('summary') or data.get('summary_recap') or f"Provision of {product_name} services."
    if isinstance(summary, list): summary = ". ".join(summary)
    
    proj_summary_text = f"""🔹 Overall Project Summary
Project: {real_title}
Contract Type: {contract_type}
Performance Period: {delivery_period}
Work Includes: {summary}"""

    proj_summary_html = f"""<h3>🔹 Overall Project Summary</h3>
<ul>
<li><b>Project:</b> {real_title}</li>
<li><b>Contract Type:</b> {contract_type}</li>
<li><b>Performance Period:</b> {delivery_period}</li>
<li><b>Work Includes:</b> {summary}</li>
</ul>"""

    # --- SECTION 10: Base Contract Scope ---
    # Try to group CLINs by years if possible, else just list them
    clins = data.get('clins', [])
    scope_clins_text = "⚙️ Base Contract Scope\n"
    scope_clins_html = "<h3>⚙️ Base Contract Scope</h3><ul>"
    
    if clins:
        for c in clins[:15]: # Show first 15 CLINs
            c_num = c.get('clin') or c.get('clin_number', '')
            c_desc = c.get('description', '')
            c_qty = c.get('quantity', '')
            c_unit = c.get('unit', '')
            line = f"   • {c_num} {c_desc} - {c_qty} {c_unit}\n"
            scope_clins_text += line
            scope_clins_html += f"<li>{c_num} {c_desc} - {c_qty} {c_unit}</li>"
    else:
        scope_clins_text += "   • Scope as defined in technical specifications and PWS.\n"
        scope_clins_html += "<li>Scope as defined in technical specifications and PWS.</li>"
    
    scope_clins_html += "</ul>"

    # --- SECTION 11: Totals Required on Bid Form ---
    totals_text = f"""📘 Totals Required on Bid Form
Total Base Contract Amount
Total Option Amount (if applicable)
Combined Total"""

    totals_html = f"""<h3>📘 Totals Required on Bid Form</h3>
<ul>
<li>Total Base Contract Amount</li>
<li>Total Option Amount (if applicable)</li>
<li>Combined Total</li>
</ul>"""

    # --- SECTION 12: Key Takeaways for Bidder ---
    takeaways_text = f"""💡 Key Takeaways for Bidder
Price all CLINs — incomplete pricing may disqualify the bid.
Include reporting and maintenance costs for each year as specified.
Confirm all submittals follow the delivery timetable and format."""

    takeaways_html = f"""<h3>💡 Key Takeaways for Bidder</h3>
<ul>
<li>Price all CLINs — incomplete pricing may disqualify the bid.</li>
<li>Include reporting and maintenance costs for each year as specified.</li>
<li>Confirm all submittals follow the delivery timetable and format.</li>
</ul>"""

    # --- SECTION 13: KEY DATES & ACTIONS FOR VENDORS (Table) ---
    timeline_data = data.get('timeline_deliverables', {})
    deadlines = timeline_data.get('reporting_deadlines', [])
    
    dates_table_text = "🔹 KEY DATES & ACTIONS FOR VENDORS\n"
    dates_table_html = "<h3>🔹 KEY DATES & ACTIONS FOR VENDORS</h3><table border='1' style='border-collapse: collapse; width: 100%;'><tr><th>Action</th><th>Deadline / Timing</th><th>Reference Doc</th></tr>"
    
    if deadlines:
        for d in deadlines[:5]:
            action = d.get('deliverable') or d.get('activity', missing_msg)
            timing = d.get('deadline') or d.get('frequency', missing_msg)
            ref = d.get('reference') or "PWS / Attachment"
            dates_table_text += f"   • {action} | {timing} | {ref}\n"
            dates_table_html += f"<tr><td>{action}</td><td>{timing}</td><td>{ref}</td></tr>"
    else:
        dates_table_text += "   • Submit all Required Plans | Within 30 days of award | Attachment 1\n"
        dates_table_html += "<tr><td>Submit all Required Plans</td><td>Within 30 days of award</td><td>Attachment 1</td></tr>"
    
    dates_table_html += "</table>"

    # --- SECTION 14: SUMMARY FOR BIDDERS / CONTRACTORS ---
    summary_bidders_text = "🔹 SUMMARY FOR BIDDERS / CONTRACTORS\nYou Will Be Responsible To:\n   • Prepare and submit all plans per schedule.\n   • Conduct services as specified in the PWS.\n   • Meet performance standards and reporting requirements."
    summary_bidders_html = "<h3>🔹 SUMMARY FOR BIDDERS / CONTRACTORS</h3><p><b>You Will Be Responsible To:</b></p><ul><li>Prepare and submit all plans per schedule.</li><li>Conduct services as specified in the PWS.</li><li>Meet performance standards and reporting requirements.</li></ul>"

    # --- ASSEMBLE FINAL EMAIL ---
    plain_body = f"""{intro_text}

{overview_text}

{scope_text}

{key_reqs_text}

{legal_text}

{submission_text}

{post_award_text}

{ref_info_text}

{proj_summary_text}

{scope_clins_text}

{totals_text}

{takeaways_text}

{dates_table_text}

{summary_bidders_text}

-----End of letter/solicitation-----"""

    html_body = f"""<html>
<body>
{intro_html}
{overview_html}
{scope_html}
{key_reqs_html}
{legal_html}
{submission_html}
{post_award_html}
{ref_info_html}
{proj_summary_html}
{scope_clins_html}
{totals_text}
{takeaways_html}
{dates_table_html}
{summary_bidders_html}
<p>-----End of letter/solicitation-----</p>
</body>
</html>"""

    return subject, plain_body, html_body


def format_email_body(sol_id, sol_title, product_name, quantity, specs, delivery_loc_json, timeline=None, description=None, due_date_str=None, sol_url=None, analysis_json=None):
    """
    Backward compatible wrapper that detects category and returns subject, plain_body, and html_body.
    Note: Now returns 3 values (subject, body, html).
    """
    category = "Service" # Default fallback
    
    # Combined text for keyword search
    text_content = (sol_title + " " + (description or "")).lower()
    
    # 1. Initial Category from Analysis or NAICS
    if analysis_json:
        try:
             a_data = json.loads(analysis_json)
             
             # Start with AI classification if available
             if a_data.get('solicitation_category') == "Product":
                 category = "Product"
             
             # NAICS Check (31, 32, 33 = Manufacturing/Product)
             naics = a_data.get('naics_code', '')
             if naics and str(naics).startswith(('31', '32', '33')):
                 category = "Product"
        except: pass
        
    # 2. Strong Keywords (Service) - Overrides NAICS if ambiguous (e.g., "Repair of Equipment")
    if any(x in text_content for x in ['maintenance', 'service', 'installation', 'repair', 'labor', 'rental', 'janitorial', 'cleaning', 'personnel', 'staffing']):
        category = "Service"
        
    # 3. Product Keywords (only if not already matched as Service in step 2)
    elif any(x in text_content for x in ['supply', 'deliver', 'hardware', 'equipment', 'parts', 'software', 'license', 'nsn', 'part number', 'procurement of']):
        category = "Product"
    
    if category == "Product":
        return format_product_email_body(sol_id, sol_title, product_name, quantity, specs, delivery_loc_json, timeline, description, due_date_str, sol_url, analysis_json)
    else:
        return format_service_email_body(sol_id, sol_title, product_name, quantity, specs, delivery_loc_json, timeline, description, due_date_str, sol_url, analysis_json)


def format_product_email_body(sol_id, sol_title, product_name, quantity, specs, delivery_loc_json, timeline=None, description=None, due_date_str=None, sol_url=None, analysis_json=None):
    """
    Formats the email body for PRODUCT solicitations matching Claude Vendor List.odt format exactly.
    Returns: subject, plain_body, html_body
    """
    today_str = datetime.date.today().strftime("%B %d, %Y")
    missing_msg = "Information not provided in solicitation"
    
    # Parse Analysis Data
    data = {}
    if analysis_json:
        try:
            data = json.loads(analysis_json)
        except: pass

    # Extract key fields
    notice_id = data.get('notice_id') or data.get('contract_id') or sol_id
    real_title = data.get('title') or sol_title
    quotes_due = due_date_str or clean_val(data.get('quotes_due_date'), missing_msg)
    internal_deadline = calculate_internal_deadline(quotes_due)
    
    # Get product details
    p_details = data.get('product_details', {})
    if isinstance(p_details, list) and p_details:
        p_details = p_details[0]
    elif not isinstance(p_details, dict):
        p_details = {}
    
    # --- SUBJECT ---
    subject = f"Request for Quote - {real_title} ({notice_id})"
    
    # --- SECTION 1: HEADER & INTRO ---
    intro_text = f"""Dear Vendor,

We are writing to request a formal quote for {product_name}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

If you have any questions regarding this request or need additional information, please contact me at {SENDER_EMAIL}. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

[Contracting Team]"""

    intro_html = f"""<p>Dear Vendor,</p>
<p>We are writing to request a formal quote for {product_name}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.</p>
<p>If you have any questions regarding this request or need additional information, please contact me at {SENDER_EMAIL}. We look forward to establishing a mutually beneficial business relationship.</p>
<p>Thank you for your time and consideration.</p>
<p>[Contracting Team]</p>"""

    # --- SECTION 2: OVERVIEW ---
    agency_name = data.get('soliciting_entity') or "Defense Logistics Agency (DLA)"
    agency_address = data.get('issuing_agency_address') or ""
    contract_type = clean_val(data.get('contract_type'), "Firm Fixed Price")
    set_aside = clean_val(data.get('set_aside_type'), "100% Small Business Set-Aside")
    sol_date = clean_val(data.get('solicitation_date'), missing_msg)
    naics = clean_val(data.get('naics_code'), missing_msg)
    size_std = clean_val(data.get('size_standard'), missing_msg)
    dpas = clean_val(data.get('dpas_rating'), "DO-A4 (Defense Priority and Allocation System)")
    
    overview_text = f"""🔹 Overview
Agency Issuing RFQ: {agency_name}
{agency_address}
Type of Contract: {contract_type}
Set-Aside Type: {set_aside}
Solicitation Date: {sol_date}
Quotes Due: {quotes_due}
Solicitation Title: {real_title}
Contract Number (if awarded): {notice_id}
NAICS Code: {naics}
Size Standard: {size_std}
DPAS Rating: {dpas}"""

    overview_html = f"""<h3>🔹 Overview</h3>
<ul>
<li><b>Agency Issuing RFQ:</b> {agency_name}<br>{agency_address}</li>
<li><b>Type of Contract:</b> {contract_type}</li>
<li><b>Set-Aside Type:</b> {set_aside}</li>
<li><b>Solicitation Date:</b> {sol_date}</li>
<li><b>Quotes Due:</b> {quotes_due}</li>
<li><b>Solicitation Title:</b> {real_title}</li>
<li><b>Contract Number (if awarded):</b> {notice_id}</li>
<li><b>NAICS Code:</b> {naics}</li>
<li><b>Size Standard:</b> {size_std}</li>
<li><b>DPAS Rating:</b> {dpas}</li>
</ul>"""

    # --- SECTION 3: ITEMS REQUIRED ---
    mfg_cage = clean_val(p_details.get('manufacturer_cage'), missing_msg)
    part_number = clean_val(p_details.get('manufacturer_part_number'), missing_msg)
    nsn = clean_val(p_details.get('nsn'), missing_msg)
    item_desc = clean_val(p_details.get('description') or p_details.get('technical_description'), "Standard item for military use")
    
    items_text = f"""🔹 Items Required
Item Requested: {product_name}
Manufacturer CAGE: {mfg_cage}
Manufacturer Part Number: {part_number}
Description: {item_desc}"""

    items_html = f"""<h3>🔹 Items Required</h3>
<ul>
<li><b>Item Requested:</b> {product_name}</li>
<li><b>Manufacturer CAGE:</b> {mfg_cage}</li>
<li><b>Manufacturer Part Number:</b> {part_number}</li>
<li><b>Description:</b> {item_desc}</li>
</ul>"""

    # --- SECTION 4: CLIN TABLE ---
    clins = data.get('clins', [])
    if clins:
        clin_text = "\n🔹 Contract Line Items (CLINs)\n"
        clin_html = "<h3>🔹 Contract Line Items (CLINs)</h3><table border='1' style='border-collapse: collapse; width: 100%;'><tr><th>CLIN</th><th>Description</th><th>Quantity (EA)</th><th>Contract Type</th><th>Inspection/Acceptance</th><th>Packaging</th><th>Notes</th></tr>"
        
        for clin in clins:
            clin_num = clin.get('clin', missing_msg)
            desc = clin.get('description', product_name)
            qty = clin.get('quantity', missing_msg)
            unit = clin.get('unit', 'EA')
            pkg = clin.get('packaging', 'Military, Level B')
            notes = clin.get('notes', '')
            
            clin_text += f"   • CLIN: {clin_num} | Description: {desc} | Quantity: {qty} {unit} | Contract Type: FFP | Inspection/Acceptance: Origin | Packaging: {pkg} | Notes: {notes}\n"
            clin_html += f"<tr><td>{clin_num}</td><td>{desc}</td><td>{qty} {unit}</td><td>FFP</td><td>Origin</td><td>{pkg}</td><td>{notes}</td></tr>"
        
        clin_html += "</table>"
    else:
        clin_text = f"\n🔹 Contract Line Items (CLINs)\nQuantity: {quantity}\n"
        clin_html = f"<h3>🔹 Contract Line Items (CLINs)</h3><p>Quantity: {quantity}</p>"

    # --- SECTION 5: INSPECTION & TESTING ---
    insp = data.get('inspection_testing', {})
    insp_point = clean_val(insp.get('point') or insp.get('inspection_point'), "Origin")
    accept_point = clean_val(insp.get('acceptance_point'), "Origin")
    insp_agency = clean_val(insp.get('agency'), "DCMA (Defense Contract Management Agency)")
    ipi_required = insp.get('ipi_required', False)
    quality_std = clean_val(insp.get('quality_standard'), "ISO 9001:2015 or equivalent")
    
    inspection_text = f"""🔹 Inspection & Testing
Inspection Point: {insp_point}
Acceptance Point: {accept_point}
Inspection Agency: {insp_agency}
Requirement: Notify DCMA for inspection before shipping
Initial Production Inspection (IPI): {"Required" if ipi_required else "May be required"}
Quality Standard: {quality_std}"""

    inspection_html = f"""<h3>🔹 Inspection & Testing</h3>
<ul>
<li><b>Inspection Point:</b> {insp_point}</li>
<li><b>Acceptance Point:</b> {accept_point}</li>
<li><b>Inspection Agency:</b> {insp_agency}</li>
<li><b>Requirement:</b> Notify DCMA for inspection before shipping</li>
<li><b>Initial Production Inspection (IPI):</b> {"Required" if ipi_required else "May be required"}</li>
<li><b>Quality Standard:</b> {quality_std}</li>
</ul>"""

    # --- SECTION 6: DELIVERY REQUIREMENTS ---
    deliv = data.get('delivery_requirements', {})
    fob_point = clean_val(deliv.get('fob_point'), "Destination")
    ship_to = clean_val(deliv.get('ship_to_address'), missing_msg)
    schedule_aro = clean_val(deliv.get('schedule_aro'), "340 days ARO")
    frequency = clean_val(deliv.get('frequency'), "24 units every 30 days")
    
    delivery_text = f"""🔹 Delivery Requirements
General Delivery Terms
FOB Point: {fob_point}
Destination: Ship to {ship_to}
Inspection: {insp_point}
Acceptance: {accept_point}

Delivery Schedule
Delivery must begin: {schedule_aro}
Deliveries to continue: {frequency}
Acceleration: Early delivery accepted at no extra cost"""

    delivery_html = f"""<h3>🔹 Delivery Requirements</h3>
<h4>General Delivery Terms</h4>
<ul>
<li><b>FOB Point:</b> {fob_point}</li>
<li><b>Destination:</b> Ship to {ship_to}</li>
<li><b>Inspection:</b> {insp_point}</li>
<li><b>Acceptance:</b> {accept_point}</li>
</ul>
<h4>Delivery Schedule</h4>
<ul>
<li><b>Delivery must begin:</b> {schedule_aro}</li>
<li><b>Deliveries to continue:</b> {frequency}</li>
<li><b>Acceleration:</b> Early delivery accepted at no extra cost</li>
</ul>"""

    # --- SECTION 7: DATA & ACCESS REQUIREMENTS ---
    tdp_available = p_details.get('tdp_access') or data.get('data_access_requirements', {}).get('tdp_available', False)
    jcp_required = data.get('compliance', {}).get('jcp_certification_required', False)
    
    data_access_text = f"""🔹 Data & Access Requirements
Technical Data Package (TDP) available via SAM.gov link
Suppliers must have a current DD2345 (JCP Certification) for militarily critical technical data
Suppliers must follow ITAR/export-controlled document handling procedures"""

    data_access_html = f"""<h3>🔹 Data & Access Requirements</h3>
<ul>
<li>Technical Data Package (TDP) available via SAM.gov link</li>
<li>Suppliers must have a current DD2345 (JCP Certification) for militarily critical technical data</li>
<li>Suppliers must follow ITAR/export-controlled document handling procedures</li>
</ul>"""

    # --- SECTION 8: SUBMISSION DETAILS ---
    submission_text = f"""🔹 Submission Details
Quote Submission: Email proposal (PDF preferred) to {SENDER_EMAIL}
Subject line: Proposal Submission {notice_id} (Company Name)
Due Date: {internal_deadline}
Evaluation Basis: Lowest price, technically acceptable (LPTA)
"All or None" clause applies — partial bids not accepted"""

    submission_html = f"""<h3>🔹 Submission Details</h3>
<ul>
<li><b>Quote Submission:</b> Email proposal (PDF preferred) to {SENDER_EMAIL}</li>
<li><b>Subject line:</b> Proposal Submission {notice_id} (Company Name)</li>
<li><b>Due Date:</b> {internal_deadline}</li>
<li><b>Evaluation Basis:</b> Lowest price, technically acceptable (LPTA)</li>
<li>"All or None" clause applies — partial bids not accepted</li>
</ul>"""

    # --- SECTION 9: SUMMARY OF WHAT THEY REQUIRE ---
    summary_text = f"""🔹 Summary of What They Require
In Plain Terms:
   • Supply {product_name} built to military specifications
   • Meet {quality_std} quality standard
   • Inspect and accept at origin, coordinate with DCMA before shipment
   • Deliver to {ship_to} FOB {fob_point}
   • Lead time: {schedule_aro}
   • Follow special packaging, preservation, and labeling per MIL-STD-2073-1 & MIL-STD-129
   • Maintain traceability documentation for 10 years after final payment
   • Possess approved JCP certification to access restricted Technical Data Packages (TDPs)"""

    summary_html = f"""<h3>🔹 Summary of What They Require</h3>
<p><b>In Plain Terms:</b></p>
<ul>
<li>Supply {product_name} built to military specifications</li>
<li>Meet {quality_std} quality standard</li>
<li>Inspect and accept at origin, coordinate with DCMA before shipment</li>
<li>Deliver to {ship_to} FOB {fob_point}</li>
<li>Lead time: {schedule_aro}</li>
<li>Follow special packaging, preservation, and labeling per MIL-STD-2073-1 & MIL-STD-129</li>
<li>Maintain traceability documentation for 10 years after final payment</li>
<li>Possess approved JCP certification to access restricted Technical Data Packages (TDPs)</li>
</ul>"""

    # --- ASSEMBLE FINAL EMAIL ---
    plain_body = f"""{intro_text}

{overview_text}

{items_text}

{clin_text}

{inspection_text}

{delivery_text}

{data_access_text}

{submission_text}

{summary_text}

-----End of letter/solicitation-----"""

    html_body = f"""<html>
<body>
{intro_html}
{overview_html}
{items_html}
{clin_html}
{inspection_html}
{delivery_html}
{data_access_html}
{submission_html}
{summary_html}
<p>-----End of letter/solicitation-----</p>
</body>
</html>"""

    return subject, plain_body, html_body

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
    # Join with product_suppliers to filter out 'invalid' matches
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
            s.data,
            s.url,
            p.id as product_id
        FROM manufacturer_requests r
        JOIN manufacturers m ON r.manufacturer_id = m.id
        JOIN products p ON r.product_id = p.id
        JOIN product_suppliers ps ON (p.id = ps.product_id AND m.id = ps.manufacturer_id)
        LEFT JOIN solicitations s ON p.contract_id = s.contract_id
        WHERE (r.status = 'pending' OR r.status = 'failed')
          AND m.email IS NOT NULL 
          AND m.email != ''
          AND ps.validation_status != 'invalid'
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
        req_id, email_addr, product_name, quantity, specs, contract_id, mfg_name, sol_title, analysis_json, sol_data_json, sol_url, product_id = task
        
        # QUALITY GATE: Verify this solicitation has PDF attachments
        # Skip solicitations with only SAM.gov HTML scrapes (no detailed data)
        cursor.execute("SELECT COUNT(*) FROM attachments WHERE contract_id = ?", (contract_id,))
        attachment_count = cursor.fetchone()[0]
        
        if attachment_count == 0:
            logger.warning(f"⚠️  Skipping {contract_id} - No PDF attachments (incomplete data)")
            cursor.execute("UPDATE manufacturer_requests SET status = 'skipped_incomplete' WHERE id = ?", (req_id,))
            conn.commit()
            continue

        # --- NEW QUALITY GATES (Step Id: 512) ---
        # 1. Reject Award Notices
        bad_keywords = ["AWARD NOTICE", "NOTICE OF AWARD", "JUSTIFICATION AND APPROVAL", "J&A", "INTENT TO SOLE SOURCE"]
        if any(bad in sol_title.upper() for bad in bad_keywords):
            logger.warning(f"⛔ Skipping {contract_id} - Identified as Award/Admin Notice: '{sol_title}'")
            cursor.execute("UPDATE manufacturer_requests SET status = 'skipped_award_notice' WHERE id = ?", (req_id,))
            conn.commit()
            continue
        
        # Parse Analysis Once
        data = {}
        if analysis_json:
            try:
                data = json.loads(analysis_json)
            except: pass

        # 2. Minimum Viable Product Check
        p_details = data.get('product_details', [])
        # Check if list is empty or if it contains only empty/default objects
        has_valid_product = False
        if p_details and isinstance(p_details, list):
             for p in p_details:
                 if p.get('name') and p.get('name') != "Unknown Product":
                     has_valid_product = True
                     break
        
        if not has_valid_product:
            logger.warning(f"⛔ Skipping {contract_id} - No valid products extracted.")
            cursor.execute("UPDATE manufacturer_requests SET status = 'skipped_no_products' WHERE id = ?", (req_id,))
            conn.commit()
            continue

        # 3. Content Length Check (Description/Summary)
        # Using extraction or summary
        desc_check = description_str or data.get('summary', '') or specs
        if not desc_check or len(str(desc_check)) < 20:
             logger.warning(f"⛔ Skipping {contract_id} - Description too short (<20 chars). Low data quality.")
             cursor.execute("UPDATE manufacturer_requests SET status = 'skipped_low_quality' WHERE id = ?", (req_id,))
             conn.commit()
             continue
             
        # --- END QUALITY GATES ---
        
        real_specs = specs # Initial Specs
        # Parse analysis to get exact delivery location dictionary if possible
        delivery_loc_json = None
        timeline_str = None
        description_str = None
        
        if analysis_json:
             try:
                 data = json.loads(analysis_json)
                 
                 # 1. Delivery Location
                 if data.get('delivery_location'):
                     delivery_loc_json = json.dumps(data.get('delivery_location'))
                 
                 # 2. Timeline
                 if data.get('delivery_timeline'):
                      timeline_str = data.get('delivery_timeline')
                 
                 # 3. Product Details (Granular Extraction)
                 p_details = data.get('product_details', [])
                 if p_details and isinstance(p_details, list):
                     extracted_specs = []
                     total_qty = 0
                     descriptions = []
                     
                     for item in p_details:
                         # Specs + Description
                         combined_item_info = []
                         if item.get('specifications'):
                             combined_item_info.extend(item.get('specifications'))
                         if item.get('description') and len(item.get('description')) > 10:
                             combined_item_info.append(item.get('description'))
                         
                         if combined_item_info:
                             extracted_specs.append(" | ".join(combined_item_info))
                         
                         # Quantity
                         try:
                             q = item.get('quantity')
                             if q: total_qty += float(str(q).replace(',','').split()[0])
                         except: pass
                         
                         # Description List (for opener)
                         if item.get('description'):
                             descriptions.append(item.get('description'))
                     
                     # Construct Fields
                     if extracted_specs:
                         real_specs = "; ".join(extracted_specs)
                         logger.info(f"  > Extracted {len(extracted_specs)} specific specs/desc from JSON.")
                     
                     if total_qty > 0:
                         quantity = str(int(total_qty)) if total_qty.is_integer() else str(total_qty)
                         if p_details[0].get('unit'): quantity += f" {p_details[0].get('unit')}"
                     
                     if descriptions:
                         description_str = "; ".join(descriptions[:3]) # Limit to top 3 to avoid huge emails
                 
                 # Fallback: Summary
                 if not description_str and data.get('summary'): 
                     description_str = data.get('summary')

                 # 4. Deep Extraction of Real Notice ID from 'data' field
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
                             logger.info(f"  > Using Real Notice ID: {contract_id}")
                     except: pass

             except Exception as e:
                 logger.warning(f"Failed to parse analysis JSON for {contract_id}: {e}")
        
        # --- NEW: Just-In-Time Deep Spec Enrichment ---
        if product_id and (not real_specs or "DEEP SPECS" not in real_specs):
            import re
            nsn_match = re.search(r"(\d{4}-\d{2}-\d{3}-\d{4}|\d{13})", real_specs or "")
            if nsn_match:
                logger.info(f"  > Weak Specs with NSN detected for {product_id}. Triggering DeepSpecAgent...")
                spec_agent = DeepSpecAgent()
                if spec_agent.enrich_product_specs(product_id):
                    # Re-fetch enriched specs from DB
                    cursor.execute("SELECT specifications FROM products WHERE id = ?", (product_id,))
                    updated_row = cursor.fetchone()
                    if updated_row:
                        real_specs = updated_row[0]
                        logger.info(f"  > Successfully enriched with Deep Specs.")
        # ----------------------------------------------
        
        # Parse sol_data to get due_date
        due_date_str = None
        if sol_data_json:
            try:
                sdata = json.loads(sol_data_json)
                due_date_str = sdata.get('due_date')
            except: pass


        # --- ANTI-SPAM CHECK ---
        # User complained about receiving duplicate emails.
        # Check if we have sent ANY email to this address in the last 48 hours.
        cursor.execute("""
            SELECT count(*) 
            FROM manufacturer_requests r
            JOIN manufacturers m ON r.manufacturer_id = m.id
            WHERE r.status = 'sent' 
            AND m.email = ? 
            AND r.response_date > datetime('now', '-48 hours')
        """, (email_addr,))
        recent_count = cursor.fetchone()[0]
        
        if recent_count > 0:
            logger.warning(f"Skipping {email_addr}: Recently contacted (Anti-Spam Prevention).")
            # Mark as skipped or failed to remove from queue
            cursor.execute("UPDATE manufacturer_requests SET status = 'skipped_spam', notes = 'Anti-Spam: Contacted in last 48h' WHERE id = ?", (req_id,))
            conn.commit()
            fail_count += 1
            continue
        # -----------------------

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
        # Logic: If specs are empty/N/A, try to fallback to Description/Analysis Summary.
        
        if not real_specs or len(real_specs) < 15 or real_specs in ["As per standard specifications", "N/A", "None", "See Solicitation"]:
             # FAILSAFE 1: Use the Solicitation Summary
             if analysis_json:
                 try:
                     a_data = json.loads(analysis_json)
                     summary = a_data.get('summary')
                     if summary and len(summary) > 20:
                         real_specs = summary
                         logger.info(f"  > Enhanced Specs for {mfg_name} using Analysis Summary.")
                 except: pass

        # FAILSAFE 2: If we have "Drawings not available" text, we MUST append the product name and description
        if "Drawings or technical data are not available" in (real_specs or ""):
             if analysis_json:
                 try:
                     a_data = json.loads(analysis_json)
                     p_names = [p.get('name') for p in a_data.get('product_details', []) if p.get('name')]
                     if p_names:
                         # Append product names to provide context
                         context_str = f"Specific Items requested: {', '.join(p_names)}"
                         real_specs = f"{real_specs} | {context_str}"
                         logger.info(f"  > Appended product names to vague spec for {mfg_name}.")
                 except: pass
            
        # STRICT QUALITY GATE
        # If we still don't have enough detail (e.g. < 40 chars), DO NOT SEND.
        if not real_specs or len(real_specs) < 40:
             logger.warning(f"QC FAILED for {mfg_name}: Product info too vague (Len: {len(real_specs) if real_specs else 0}).")
             cursor.execute("UPDATE manufacturer_requests SET status = 'failed', notes = 'QC Failed: Insufficient Description' WHERE id = ?", (req_id,))
             conn.commit()
             fail_count += 1
             continue
        # --- VALIDATION END ---

        # Handle missing solicitation data (Left Join)
        display_id = contract_id
        display_title = sol_title if sol_title else f"Solicitation {contract_id}"
        
        # Enhanced Product Name: "Solicitation Title [Product Name]"
        # This gives the vendor immediate context (e.g. "USACE Forest MATOC [Direct Seeding]")
        enhanced_product_name = f"{display_title} [{product_name}]"
        
        # --- DYNAMIC TEMPLATE SELECTION ---
        # Determine Category: Product or Service
        category = "Service" # Default
        if analysis_json:
             try:
                 a_data = json.loads(analysis_json)
                 # 1. Explicit LLM Category
                 if a_data.get('solicitation_category'):
                     category = a_data.get('solicitation_category')
                 # 2. NAICS Logic (31, 32, 33 = Mfg = Product)
                 elif a_data.get('naics_code'):
                     naics = str(a_data.get('naics_code'))
                     if naics.startswith(('31', '32', '33')):
                         category = "Product"

                 # 3. Explicit Keyword Overrides (Stronger than Generic)
                 # Services Decision Keywords: PWS, SOW, maintenance, planting, monitoring, establish, manage
                 service_keywords = ['pws', 'sow', 'performance work statement', 'statement of work', 'maintenance', 'planting', 'monitoring', 'establish', 'manage', 'labor']
                 # Product Decision Keywords: NSN, part number, CAGE, supply, equipment, material, assembly, component, hardware
                 product_keywords = ['nsn', 'part number', 'cage code', 'supply', 'equipment', 'material', 'assembly', 'component', 'hardware']
                 
                 full_text = (sol_title + " " + (description_str or "")).lower()
                 
                 if any(x in full_text for x in service_keywords):
                     category = "Service"
                 elif any(x in full_text for x in product_keywords):
                     category = "Product"
             except: pass
        
        logger.info(f"  > Detected Category: {category}")

        if category == "Product":
             subject, body, html_body = format_product_email_body(display_id, display_title, enhanced_product_name, quantity, real_specs, delivery_loc_json, timeline_str, description_str, due_date_str, sol_url, analysis_json)
        else:
             subject, body, html_body = format_service_email_body(display_id, display_title, enhanced_product_name, quantity, real_specs, delivery_loc_json, timeline_str, description_str, due_date_str, sol_url, analysis_json)
        
        try:
            success = email_service.send_email(email_addr, subject, body, html_body=html_body)
            
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
