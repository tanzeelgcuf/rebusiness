
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import config
from database_manager import DatabaseManager
import logging
import warnings

# DEPRECATION NOTICE
warnings.warn("The ProposalWriterAgent module is deprecated. RFQ generation is now handled directly by AttachmentReaderAgent.", DeprecationWarning, stacklevel=2)
print("WARNING: ai_agents/ProposalWriterAgent/proposal_writer.py is DEPRECATED and should not be used.")

import json
import re
from datetime import datetime, timedelta

def _subtract_business_days(date, days):
    """Calculate date minus business days (excluding weekends)"""
    current = date
    while days > 0:
        current -= timedelta(days=1)
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            days -= 1
    return current

def _format_product_rfq(analysis, vendor_name="Valued Supplier", internal_deadline_offset=4):
    """Format output matching Claude Vendor List.odt with 100% fidelity"""
    notice_id = analysis.get('notice_id', 'N/A')
    title = analysis.get('title', 'N/A')
    
    # Calculate internal deadline
    submission = analysis.get('submission', {})
    due_date_str = submission.get('due_date', '')
    internal_due_formatted = f"{internal_deadline_offset} business days prior"
    try:
        match = re.search(r'(\d{4}-\d{2}-\d{2})|(\d{1,2}/\d{1,2}/\d{2,4})', due_date_str)
        if match:
            date_str = match.group()
            try:
                official_due = datetime.strptime(date_str, '%Y-%m-%d')
            except:
                official_due = datetime.strptime(date_str, '%m/%d/%Y')
            internal_due = _subtract_business_days(official_due, internal_deadline_offset)
            internal_due_formatted = internal_due.strftime('%B %d, %Y')
    except:
        pass
    
    # Header / Intro
    email_intro = f"""Notice ID: {notice_id}
Subject: RFQ for {title}

Dear [Vendor]:

We are writing to request a formal quote for {title.lower()}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

John Campbell
Procurement Manager
Campsable LLC

"""

    overview = analysis.get('overview', {})
    sections = [email_intro]

    # 1. Overview
    sections.append(f"### 🔹 Overview")
    sections.append(f"| Category | Details |")
    sections.append(f"|---|---|")
    sections.append(f"| **Procuring Agency** | {overview.get('agency_name', 'Not included in solicitation')} |")
    sections.append(f"| **Agency Address** | {overview.get('agency_address', 'Not included in solicitation')} |")
    sections.append(f"| **Contract Type** | {overview.get('contract_type', 'Firm Fixed Price')} |")
    sections.append(f"| **Set-Aside Type** | {overview.get('set_aside', 'Not included in solicitation')} |")
    sections.append(f"| **Published Dates** | {overview.get('solicitation_date', 'Not included in solicitation')} |")
    sections.append(f"| **Official Deadline** | **{submission.get('due_date', 'Not included in solicitation')}** |")
    sections.append(f"| **Internal Deadline** | **{internal_due_formatted}** |")
    sections.append(f"| **NAICS Code** | {overview.get('naics_code', 'Not included in solicitation')} – {overview.get('naics_description', '')} |")
    sections.append(f"| **Size Standard** | {overview.get('size_standard', 'Not included in solicitation')} |")
    sections.append(f"| **DPAS Rating** | {overview.get('dpas_rating', 'Not included in solicitation')} |\n")

    # 2. Items Required
    specs = analysis.get('specifications', {})
    clins = analysis.get('clins', [])
    qty_range = analysis.get('quantity_range', {})

    sections.append(f"### 🔹 Items Required")
    sections.append(f"• **Item Requested:** {specs.get('item_requested', title)}")
    sections.append(f"• **Manufacturer CAGE:** {specs.get('manufacturer_cage', 'Not included in solicitation')}")
    sections.append(f"• **Manufacturer Part Number:** {specs.get('manufacturer_part_number', 'Not included in solicitation')}")
    sections.append(f"• **NSN:** {specs.get('nsn', 'Not included in solicitation')}")
    sections.append(f"• **Description:** {specs.get('description', 'Not included in solicitation')}\n")
    
    if clins:
        sections.append("| CLIN | Description | Quantity | Unit | Contract Type | Inspection | Packaging | Notes |")
        sections.append("|---|---|---|---|---|---|---|---|")
        for c in clins:
            sections.append(f"| {c.get('clin')} | {c.get('description')} | {c.get('quantity', 'N/A')} | {c.get('unit', 'EA')} | {c.get('contract_type', 'FFP')} | {c.get('inspection')} | {c.get('packaging')} | {c.get('notes')} |")
    
    sections.append(f"\n#### Quantity & Ordering Information")
    sections.append(f"| Category | Quantity | Unit |")
    sections.append(f"|---|---|---|")
    sections.append(f"| **Minimum Order Quantity** | {qty_range.get('min', 'Not included')} | EA |")
    sections.append(f"| **Maximum Order Quantity** | {qty_range.get('max', 'Not included')} | EA |")
    sections.append(f"| **Guaranteed Minimum (Contract)** | {qty_range.get('min_contract', 'Not included')} | EA |")
    sections.append(f"| **Maximum Contract Quantity** | {qty_range.get('max_contract', 'Not included')} | EA |\n")

    # 3. Packaging Requirements
    pkg = analysis.get('packaging', {})
    sections.append(f"### 🔹 Packaging Requirements")
    sections.append(f"• **Standard:** {pkg.get('mil_std', 'Not included in solicitation')}")
    sections.append(f"• **Preservation Level:** {pkg.get('preservation', 'Not included in solicitation')}")
    sections.append(f"• **Quantity per Unit:** {pkg.get('qty_per_unit', 'Not included in solicitation')}")
    sections.append(f"• **SPI Reference:** {pkg.get('spi', 'Not included in solicitation')}")
    sections.append(f"• **Labeling:** {pkg.get('labeling', 'Standard Military Labeling Required')}\n")

    # 4. Inspection & Testing
    it = analysis.get('inspection_testing', {})
    sections.append(f"### 🔹 Inspection & Testing")
    sections.append(f"• **Inspection Point:** {it.get('inspection_point', 'Not included in solicitation')}")
    sections.append(f"• **Acceptance Point:** {it.get('acceptance_point', 'Not included in solicitation')}")
    sections.append(f"• **Inspection Agency:** {it.get('inspection_agency', 'DCMA or Government')}")
    sections.append(f"• **FAT Requirement:** {it.get('fat', 'Not included in solicitation')}")
    sections.append(f"• **Quality Standard:** {it.get('quality_standard', 'ISO 9001:2015 or equivalent')}")
    sections.append(f"• **Sampling Plan:** {it.get('sampling_plan', 'MIL-STD-1916 or equivalent')}\n")

    # 5. Delivery Requirements
    dr = analysis.get('delivery_requirements', {})
    sections.append(f"### 🔹 Delivery Requirements")
    sections.append(f"• **FOB Point:** {dr.get('fob', 'Destination')}")
    sections.append(f"• **Complete Delivery Address:** {dr.get('destination_address', 'Not included in solicitation')}")
    sections.append(f"• **Delivery Schedule:** {dr.get('schedule', 'Not included in solicitation')}")
    sections.append(f"• **Acceleration:** {dr.get('acceleration', 'Not included in solicitation')}")
    sections.append(f"• **Overall Contract Duration:** {dr.get('duration', 'Not included in solicitation')}\n")

    # 6. Data & Access Requirements
    da = analysis.get('data_access', [])
    sections.append(f"### 🔹 Data & Access Requirements")
    if isinstance(da, list):
        for item in da:
            sections.append(f"• {item}")
    else:
        sections.append(f"• Technical Data Package (TDP) access via SAM.gov.")
    sections.append(f"• **JCP Certification Required:** {analysis.get('jcp_required', 'Yes (DD2345)')}")
    sections.append("")

    # 7. Required Certifications & Compliance
    certs = analysis.get('certifications', ['ISO 9001:2015', 'ITAR Compliance (if applicable)', 'JCP Certification'])
    sections.append(f"### 🔹 Required Certifications & Compliance")
    for cert in certs:
        sections.append(f"• {cert}")
    sections.append("")

    # 8. Submission Details
    sub = analysis.get('submission', {})
    sections.append(f"### 🔹 Submission Details")
    sections.append(f"• **Method:** {sub.get('method', 'Electronic Submission (Email)')}")
    sections.append(f"• **Email for Quotes:** {sub.get('email', 'john@campsable.com')}")
    sections.append(f"• **Subject Line Format:** {sub.get('subject', f'[Quote] {notice_id} - {title}')}")
    sections.append(f"• **Due Date:** **{sub.get('due_date', 'Not included')}**")
    sections.append(f"• **Internal Submission Deadline:** **{internal_due_formatted}**")
    sections.append(f"• **Submission Requirements:** {sub.get('evaluation', 'LPTA - Technical, Past Performance, Price')}\n")

    # 9. Delivery Summary Table
    summary_table = analysis.get('delivery_summary_table', [])
    sections.append(f"### 🔹 Delivery Summary Table")
    if summary_table:
        sections.append("| CLIN | Item | Quantity | Unit | Delivery Point | Frequency | Inspection | Ship-To | Notes |")
        sections.append("|---|---|---|---|---|---|---|---|---|")
        for st in summary_table:
            sections.append(f"| {st.get('clin')} | {st.get('item')} | {st.get('qty')} | {st.get('unit', 'EA')} | {st.get('delivery')} | {st.get('frequency')} | {st.get('inspection')} | {st.get('ship_to')} | {st.get('notes')} |")
    else:
        sections.append("*See CLIN table above for delivery details.*")
    sections.append("")

    # 10. Summary of What They Require
    plain_terms = analysis.get('plain_terms_summary', [])
    sections.append(f"### 🟩 SUMMARY OF WHAT THEY REQUIRE")
    if plain_terms:
        for pt in plain_terms:
            sections.append(f"• {pt}")
    else:
        sections.append("• Supply [item] per technical specifications.")
        sections.append("• Meet required quality and packaging standards.")
        sections.append("• Deliver to specified destination within timeline.")
    
    sections.append("")

    # 11. Key Takeaways for Bidders
    takeaways = analysis.get('key_takeaways', [])
    if not takeaways:
        takeaways = [
            f"Item: {specs.get('item_requested', title)}",
            "Exact part number and CAGE compliance required",
            "Quality standard: ISO 9001:2015 (or equivalent) mandatory",
            f"Delivery terms: FOB {dr.get('fob', 'Destination')}",
            "Strict adherence to ASTM D3951 and labeling requirements",
            "ITAR / JCP certification mandatory (if applicable)",
            "CMMC Level 1 Self-Assessment required prior to award",
            f"Internal quote deadline: {internal_due_formatted}",
            "Wide Area WorkFlow (WAWF) participation required"
        ]
    sections.append(f"### 🟩 KEY TAKEAWAYS FOR BIDDERS")
    for i, t in enumerate(takeaways, 1):
        sections.append(f"{i}. {t}")

    sections.append("\n-----------")
    sections.append("End of solicitation details.")

    full_body = "\n".join(sections)
    return {"subject": f"RFQ: {notice_id} - {title}", "body": full_body}


def _format_service_rfq(analysis, vendor_name="Valued Supplier", internal_deadline_offset=4):
    """Format output matching Claude Services List.odt with 100% fidelity"""
    notice_id = analysis.get('notice_id', 'N/A')
    title = analysis.get('project_title', 'N/A')
    
    # Calculate internal deadline
    submission = analysis.get('bid_instructions', analysis.get('bid_submission', {}))
    due_date_str = submission.get('due_date', '')
    internal_due_formatted = f"{internal_deadline_offset} business days prior"
    try:
        match = re.search(r'(\d{4}-\d{2}-\d{2})|(\d{1,2}/\d{1,2}/\d{2,4})', due_date_str)
        if match:
            date_str = match.group()
            try:
                official_due = datetime.strptime(date_str, '%Y-%m-%d')
            except:
                official_due = datetime.strptime(date_str, '%m/%d/%Y')
            internal_due = _subtract_business_days(official_due, internal_deadline_offset)
            internal_due_formatted = internal_due.strftime('%B %d, %Y')
    except:
        pass

    # Header / Intro
    email_intro = f"""{title.upper()}
Notice ID {notice_id}

Dear [Vendor]:

We are writing to request a formal quote for {title.lower()}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

Your response is needed on or before **{internal_due_formatted}** in order for us to submit your bid.

There are other documents that I can send you, if this is a project that you would be interested in bidding. 

If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

John Campbell
Procurement Manager
Campsable LLC

"""

    overview = analysis.get('project_overview', {})
    in_sum = analysis.get('in_summary', {})
    
    # 0. IN SUMMARY (Exactly 3 bullets)
    in_summary_snippet = f"""### 🟩 IN SUMMARY
• **They want:** {in_sum.get('they_want', 'Not included in solicitation')}
• **Time frame:** {in_sum.get('time_frame', 'Not included in solicitation')}
• **Delivery locations:** {in_sum.get('delivery_locations', 'Not included in solicitation')}
"""
    sections = [email_intro, in_summary_snippet]

    # 1. Summary of Project
    sections.append(f"### 🔹 Summary of Project")
    sections.append(f"• **Title:** {overview.get('title', title)}")
    sections.append(f"• **Type:** {overview.get('type', 'Service Contract')}")
    sections.append(f"• **Purpose:** {overview.get('purpose', 'Not included in solicitation')}")
    sections.append(f"• **Location:** {overview.get('location', 'Not included in solicitation')}")
    sections.append(f"• **Total Work Area:** {overview.get('total_work_area', 'Not included in solicitation')}")
    sections.append(f"• **Project Objective:** {overview.get('objective', 'Not included in solicitation')}\n")

    # 2. What They Want (Scope of Work)
    scope_table = analysis.get('scope_table', [])
    sections.append(f"### 🔹 What They Want (Scope of Work)")
    if scope_table:
        sections.append("| Category | Main Tasks |")
        sections.append("|---|---|")
        for s in scope_table:
            sections.append(f"| {s.get('category')} | {s.get('main_tasks')} |")
    else:
        sections.append("*As specified in the PWS*")
    sections.append("")

    # 3. Timeline / Period of Performance
    timeline = analysis.get('timeline_table', [])
    sections.append(f"### 🔹 Timeline / Period of Performance")
    if timeline:
        sections.append("| Year | Dates | Requirements |")
        sections.append("|---|---|---|")
        for t in timeline:
            sections.append(f"| **{t.get('year')}** | {t.get('dates')} | {t.get('requirements')} |")
    else:
        sections.append("*To be determined at award*")
    sections.append("")

    # 4. Deliverables & Reporting Deadlines
    deliverables = analysis.get('deliverables_table', [])
    sections.append(f"### 🔹 Deliverables & Reporting Deadlines")
    if deliverables:
        sections.append("| Deliverable | Quantity | Deadline | Format | Submit To | Notes |")
        sections.append("|---|---|---|---|---|---|")
        for d in deliverables:
            sections.append(f"| {d.get('deliverable')} | {d.get('quantity', '1')} | {d.get('due_from_award')} | {d.get('format')} | {d.get('submit_to')} | {d.get('notes')} |")
    else:
        sections.append("*Standard reporting as per PWS*")
    sections.append("")

    # 5. Delivery / Work Locations
    work_locations = analysis.get('work_locations', {})
    sites = work_locations.get('sites', [])
    sections.append(f"### 🔹 Delivery / Work Locations")
    sections.append(f"**Summary:** {work_locations.get('summary', 'Not included in solicitation')}")
    if sites:
        sections.append("\n| Site ID | Location | Type | Acreage |")
        sections.append("|---|---|---|---|")
        for s in sites:
            sections.append(f"| {s.get('site_id')} | {s.get('location')} | {s.get('planting_type', 'N/A')} | {s.get('acreage')} |")
    sections.append("")

    # 6. Key Compliance Points
    compliance = analysis.get('compliance_points', [])
    sections.append(f"### 🔹 Key Compliance Points")
    if compliance:
        for c in compliance:
            sections.append(f"• {c}")
    else:
        sections.append("• Standard government security and performance compliance applies.")
    sections.append("")

    # 7. Acceptance Criteria
    criteria = analysis.get('acceptance_criteria', [])
    sections.append(f"### 🔹 Acceptance Criteria")
    if criteria:
        for c in criteria:
            sections.append(f"• {c}")
    else:
        sections.append("• Government inspection and acceptance per PWS standards.")
    sections.append("")

    # 8. Removed Duplicate In Summary

    # 9. General Overview
    sections.append(f"### 🔹 General Overview")
    sections.append(f"• **Agency:** {overview.get('agency', 'Not included in solicitation')}")
    sections.append(f"• **Solicitation Identification:** {notice_id}")
    sections.append(f"• **NAICS:** {analysis.get('naics', 'Not included')}\n")

    # 10. Key Requirements
    wages = analysis.get('wage_labor', {})
    insurance = analysis.get('insurance', {})
    security = analysis.get('security_compliance', {})

    sections.append(f"### 🔹 KEY REQUIREMENTS")
    
    sections.append("#### Certification & Capability")
    sections.append(f"• {analysis.get('cert_capability', 'Standard industry certifications required.')}")
    
    sections.append("\n#### Technical Standards")
    sections.append(f"• {analysis.get('tech_standards', 'Compliance with all government technical standards.')}")

    sections.append("\n#### Packaging & Labeling")
    sections.append(f"• {analysis.get('packaging_labeling', 'Standard commercial packaging or as specified in PWS.')}")

    sections.append("\n#### Wage & Labor Compliance")
    sections.append(f"• **Applicable Wage Determination:** {wages.get('type', 'Service Contract Act')}")
    if wages.get('states'):
        sections.append(f"• **States:** {', '.join(wages.get('states'))}")
    sections.append(f"• **Notes:** {wages.get('notes', 'Not included in solicitation')}")
    
    sections.append("\n#### Security & Compliance")
    for req in security.get('requirements', []):
        sections.append(f"• {req}")
    if security.get('training_deadline'):
        sections.append(f"• Deadline: {security.get('training_deadline')}")

    sections.append("\n#### Insurance Requirements")
    sections.append(f"• **General Liability:** {insurance.get('general_liability', 'Not included')}")
    sections.append(f"• **Auto Liability:** {insurance.get('auto_liability', 'Not included')}")
    sections.append(f"• **Workers’ Compensation:** {insurance.get('workers_comp', 'Not included')}")
    sections.append(f"• **Employer’s Liability:** {insurance.get('employers_liability', 'Not included')}")
    sections.append("")

    # 11. Bid Submission Instructions
    bid_ins = analysis.get('bid_instructions', {})
    sections.append(f"### 🔹 BID SUBMISSION INSTRUCTIONS")
    
    sections.append("#### Submission Method & Contact")
    sections.append(f"• **Format:** {bid_ins.get('delivery_options', 'Email proposal (PDF)')}")
    sections.append(f"• **Email Address:** john@campsable.com")
    sections.append(f"• **Deadline:** **{bid_ins.get('due_date', due_date_str)}**")
    
    sections.append("\n#### Required Quote Content")
    req_docs = bid_ins.get('required_with_bid', ['Technical Proposal', 'Past Performance', 'Price Proposal'])
    for i, doc in enumerate(req_docs, 1):
        sections.append(f"{i}. {doc}")
    
    sections.append("\n#### Evaluation Criteria")
    sections.append(f"• {analysis.get('evaluation_criteria', 'Lowest Price Technically Acceptable (LPTA)')}\n")

    # 12. ⚙️ BASE CONTRACT SCOPE
    clins = analysis.get('clins_breakdown', {})
    base_clins = clins.get('base', [])
    sections.append(f"### 🔹 ⚙️ BASE CONTRACT SCOPE")
    if base_clins:
        sections.append("| CLIN | Item Description | Quantity | Unit | Notes |")
        sections.append("|---|---|---|---|---|")
        for c in base_clins:
            sections.append(f"| {c.get('clin')} | {c.get('description')} | {c.get('qty')} | {c.get('unit')} | {c.get('notes', '')} |")
    else:
        sections.append("*Refer to SF 1449 for itemized base pricing.*")
    sections.append("")

    # 13. 🟩 OPTION 1 SCOPE
    option_clins = clins.get('options', [])
    sections.append(f"### 🔹 🟩 OPTION 1 SCOPE")
    if option_clins:
        sections.append("| CLIN | Item Description | Quantity | Unit | Notes |")
        sections.append("|---|---|---|---|---|")
        for c in option_clins:
            sections.append(f"| {c.get('clin')} | {c.get('description')} | {c.get('qty')} | {c.get('unit')} | {c.get('notes', '')} |")
    else:
        sections.append("**Not Included in This Solicitation** - This contract does not include option periods.")
    sections.append("")

    # 14. ATTACHMENTS PROVIDED
    attachments = analysis.get('attachments', [])
    sections.append(f"### 🔹 ATTACHMENTS PROVIDED")
    if attachments:
        for idx, att in enumerate(attachments, 1):
            sections.append(f"{idx}. **{att.get('title')}**: {att.get('purpose', 'Technical details/specifications')}")
    else:
        sections.append("*Main solicitation document only.*")
    sections.append("")

    # 15. Summary for Bidders
    bidder_summary = analysis.get('summary_for_bidders', [])
    if not bidder_summary:
        bidder_summary = [
            "Review Statement of Work (SOW) / PWS for detailed tasks",
            "Verify all required certifications (FAA, OEM, ISO) are current",
            "Comply with all safety, security, and labor wage requirements",
            "Submit technical and pricing volumes per instructions",
            "Ensure delivery is within the required Period of Performance",
            "Confirm acceptance points and inspection agency requirements",
            f"Internal deadline for submission: {internal_due_formatted}",
            "Quote must remain valid for at least 90 days"
        ]
    sections.append(f"### � SUMMARY FOR BIDDERS")
    for i, s in enumerate(bidder_summary, 1):
        sections.append(f"{i}. {s}")
    
    # 16. KEY TAKEAWAYS FOR BIDDER
    key_takeaways = analysis.get('key_takeaways', bidder_summary)
    sections.append(f"\n### 🟩 KEY TAKEAWAYS FOR BIDDER")
    for s in key_takeaways:
        sections.append(f"- [ ] {s}")

    sections.append("\n----end of RFQ-----")

    full_body = "\n".join(sections)
    return {"subject": f"{title.upper()} - Notice ID {notice_id}", "body": full_body}


def create_bid_request(analysis_summary, vendor_name="Valued Supplier", internal_deadline_offset=4):
    if not isinstance(analysis_summary, dict):
        return {"subject": "Error", "body": "Invalid analysis"}
    sol_type = analysis_summary.get('solicitation_type', 'PRODUCT').upper()
    if 'PRODUCT' in sol_type:
        return _format_product_rfq(analysis_summary, vendor_name, internal_deadline_offset)
    else:
        return _format_service_rfq(analysis_summary, vendor_name, internal_deadline_offset)
