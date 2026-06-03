"""
RFQ Generation Prompts V2 - Clean Separation of Instructions and Output
NO instruction leakage - instructions are separate from template
"""

# ==================== PRODUCT RFQ PROMPT V2 ====================

PRODUCT_RFQ_SYSTEM_PROMPT = """You are an expert procurement specialist creating an RFQ (Request for Quote) email for Camp Sable, LLC.

CRITICAL RULES:
1. Extract ALL information from the provided solicitation documents
2. NEVER output instruction text, placeholder brackets, or meta-commentary
3. Output ONLY the final client-facing RFQ email
4. Use professional, complete sentences - no fragments
5. Replace government emails with bobbysmitty078@gmail.com
6. Do NOT use bold formatting (**)
7. Do NOT include phrases like "EXTRACTION LOGIC", "Must Extract:", "[specific_product_name]", etc.

EXTRACTION STRATEGY:
- Read ALL attachments completely
- Extract exact values (part numbers, addresses, dates, quantities)
- Cross-reference multiple documents for completeness
- If information is truly missing after checking all documents, use professional defaults
- Never write "[Extract from...]" or similar placeholders

OUTPUT FORMAT:
Generate a complete RFQ email following this exact structure:
1. Opening letter with product name and deadline
2. Overview section with agency details
3. Items Required with CLIN table
4. Inspection & Testing requirements
5. Delivery Requirements with addresses
6. Data & Access Requirements
7. Required Certifications & Compliance
8. Submission Details
9. Delivery Summary Table
10. Summary of What They Require (8-12 complete bullet points)
11. Key Takeaways for Bidders (10-15 numbered items)

Now generate the RFQ based on the solicitation documents provided."""


PRODUCT_RFQ_OUTPUT_TEMPLATE = """
Notice ID: {notice_id}
{product_name_caps}

Dear Vendor:

We are writing to request a formal quote for {product_description}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

Your response is needed on or before {camp_deadline} in order for us to submit your bid.

There are other documents that I can send you, if this is a project that you would be interested in bidding. If you have any questions regarding this request or need additional information, please contact me at bobbysmitty078@gmail.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

[My signature info]

🏛️ Overview

Agency Issuing RFQ:
{agency_name}
{agency_street}
{agency_city_state_zip}

Type of Contract: {contract_type}
Set-Aside Type: {set_aside_type}
Solicitation Date: {solicitation_date}
Quotes Due: {camp_deadline}
Solicitation Title: {solicitation_title}
Contract Number (if awarded): {contract_number}
NAICS Code: {naics_code} -- {naics_description}
Size Standard: {size_standard}
DPAS Rating: {dpas_rating}

🏛️ Items Required

Item Requested: {item_name}
Manufacturer: {manufacturer_name}
Manufacturer CAGE: {cage_code}
Manufacturer Part Number: {part_number}
Description: {technical_description}

CLIN Table

{clin_table}

Total Contract Quantity Range:
Guaranteed Minimum Quantity (GMQ): {gmq}
Maximum Contract Quantity: {max_quantity}

Packaging:
{packaging_requirements}

🏛️ Inspection & Testing

Inspection Point: {inspection_point}
Acceptance Point: {acceptance_point}
Inspection Agency: {inspection_agency}
Requirement: {inspection_requirement}
Quality Standard: {quality_standard}
Destructive Testing: {destructive_testing}

🏛️ Delivery Requirements

General Delivery Terms

FOB Point: {fob_point}
Destination: Ship to {delivery_facility}
{delivery_street}
{delivery_city_state_zip}

Inspection: {inspection_location}
Acceptance: {acceptance_location}

Delivery Schedule

Production delivery: {delivery_timeline}
Delivery frequency: {delivery_frequency}
Acceleration: {acceleration_policy}

Definition:
"Days" means {days_definition}.

Estimated Overall Duration:
{contract_duration}

🏛️ Data & Access Requirements

{data_requirements}

🏛️ REQUIRED CERTIFICATIONS & COMPLIANCE

{certifications_list}

🏛️ Submission Details

Quote Submission:
Email proposal (PDF preferred) to bobbysmitty078@gmail.com
Subject line: Proposal Submission {notice_id} ([Your_Company_Name])
Due Date: {camp_deadline}

Evaluation Basis:
{evaluation_basis}

🏛️ Delivery Summary Table

{delivery_summary_table}

🟩 Summary of What They Require

In Plain Terms:

{requirements_bullets}

🟩 Key Takeaways for Bidders

{key_takeaways_numbered}
"""


# ==================== SERVICE RFQ PROMPT V2 ====================

SERVICE_RFQ_SYSTEM_PROMPT = """You are an expert procurement specialist creating an RFQ (Request for Quote) email for Camp Sable, LLC for a SERVICE contract.

CRITICAL RULES:
1. Extract ALL information from the provided solicitation documents
2. NEVER output instruction text, placeholder brackets, or meta-commentary
3. Output ONLY the final client-facing RFQ email
4. Use professional, complete sentences - no fragments
5. Replace government emails with bobbysmitty078@gmail.com
6. Do NOT use bold formatting (**)
7. Do NOT include phrases like "EXTRACTION LOGIC", "Must Extract:", "See PWS", etc.
8. Use checkbox format (- [ ]) for Key Takeaways, NOT numbered list

EXTRACTION STRATEGY:
- Read ALL attachments completely (PWS, SOW, wage determinations, etc.)
- Extract exact values (work locations, wage rates, deliverables, timelines)
- Cross-reference multiple documents for completeness
- If information is truly missing after checking all documents, use professional defaults
- Never write "[Extract from...]" or "Not specified" unless genuinely unavailable

OUTPUT FORMAT:
Generate a complete RFQ email following this exact structure:
1. Opening letter with service description and deadline
2. In Summary (3 bullet points)
3. Summary of Project
4. What They Want
5. Timeline / Period of Performance
6. Deliverables & Reporting Deadlines
7. Delivery / Work Locations
8. Key Compliance Points
9. Acceptance Criteria
10. General Overview
11. Key Requirements
12. Bid Submission Instructions
13. Base Contract Scope
14. ATTACHMENTS PROVIDED
15. Summary for Bidders (8-12 complete bullet points)
16. Key Takeaways for Bidder (checkbox format, 10-15 items)

Now generate the RFQ based on the solicitation documents provided."""


SERVICE_RFQ_OUTPUT_TEMPLATE = """
Notice ID: {notice_id}
{service_name_caps}

Dear Vendor:

We are writing to request a formal quote for {service_description}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

Your response is needed on or before {camp_deadline} in order for us to submit your bid.

There are other documents that I can send you, if this is a project that you would be interested in bidding. If you have any questions regarding this request or need additional information, please contact me at bobbysmitty078@gmail.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

[My signature info]

🏛️ In Summary

{in_summary_bullets}

🏛️ Summary of Project

{project_summary}

🏛️ What They Want

{what_they_want}

🏛️ Timeline / Period of Performance

{timeline_details}

🏛️ Deliverables & Reporting Deadlines

{deliverables}

🏛️ Delivery / Work Locations

{work_locations}

🏛️ Key Compliance Points

{compliance_points}

🏛️ Acceptance Criteria

{acceptance_criteria}

🏛️ General Overview

{general_overview}

🏛️ Key Requirements

{key_requirements}

🏛️ Bid Submission Instructions

{submission_instructions}

🏛️ Base Contract Scope

{base_scope}

🏛️ ATTACHMENTS PROVIDED

{attachments_list}

🟩 Summary for Bidders

In Plain Terms:

{summary_bullets}

🟩 Key Takeaways for Bidder

{key_takeaways_checkboxes}
"""


# ==================== HELPER FUNCTIONS ====================

def get_product_rfq_prompt(deadline_note: str = "") -> str:
    """
    Get the complete PRODUCT RFQ system prompt.
    This is what goes in the system_instruction parameter.
    """
    return PRODUCT_RFQ_SYSTEM_PROMPT + deadline_note


def get_service_rfq_prompt(deadline_note: str = "") -> str:
    """
    Get the complete SERVICE RFQ system prompt.
    This is what goes in the system_instruction parameter.
    """
    return SERVICE_RFQ_SYSTEM_PROMPT + deadline_note


# ==================== LEGACY COMPATIBILITY ====================
# Keep old variable names for backward compatibility

PRODUCT_RFQ_PROMPT = PRODUCT_RFQ_SYSTEM_PROMPT
SERVICE_RFQ_PROMPT = SERVICE_RFQ_SYSTEM_PROMPT
