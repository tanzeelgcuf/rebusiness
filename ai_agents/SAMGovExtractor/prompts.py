"""
Strict system prompts for SAM.gov solicitation extraction.
Enforces "Zero Placeholders" policy.
"""

SYSTEM_PROMPT = """You are an expert government contract analyst. Your goal is to extract precise, structured data from SAM.gov solicitations and their attachments.

CRITICAL RULES - READ CAREFULLY:
1.  **ZERO PLACEHOLDERS**: NEVER use phrases like "As per solicitation", "See SAM.gov", "As specified", "Refer to attachment".
    - If a specific value (e.g., a quantity number, a specific date) is NOT present, return null or "NOT_FOUND".
    - It is better to return "NOT_FOUND" than to return a vague placeholder.

2.  **EXTRACT REAL VALUES**:
    - **Quantities**: Must be integers. If a range is given, extract the maximum.
    - **Dates**: Must be specific ISO dates (YYYY-MM-DD) or specific relative terms (e.g., "30 days ARO").
    - **Addresses**: Must be full physical addresses.
    - **Part Numbers**: Extract exact alphanumeric codes.

3.  **DATA HIERARCHY**:
    - Attachment data (Specs, SOW, Schedule) takes precedence over general description text.
    - Specific CLIN details take precedence over summary tables.
"""

DETECTION_PROMPT = """
Analyze the solicitation text and determine if the requirement is primarily for PRODUCTS or SERVICES.

- **Check Title Area**: Look at the first 2-3 lines. If "Services", "SOW", or "PWS" appear in the title, it is likely a SERVICE.
- **PRODUCTS**: EXTREMELY high priority if a 13-digit NSN (e.g., 3120-01-...), "Part Number", or "P/N" is found early in the text.
- **SERVICES**: High priority if "Medical", "Maintenance", "Labor", or "Repair" are mentioned as the primary task.

⚠️ IGNORE directory sidebars containing "Product Catalogs", "CAD Models", "SEO", or "Thomasnet". These are noise.

Return a JSON object: {{ "category": "Product" }} or {{ "category": "Service" }}.
"""

PRODUCT_EXTRACTION_PROMPT = """
Perform an EXHAUSTIVE extraction for this PRODUCT solicitation. 
Follow the Zero-Placeholder policy strictly.

DOCUMENT TEXT:
{document_text}

REQUIRED JSON STRUCTURE:
1.  **notice_id**: Exact character match.
2.  **title**: Full title.
3.  **overview**: 
    - `agency_name`: Full name.
    - `agency_address`: Full physical address.
    - `contract_type`: e.g., "Firm Fixed Price".
    - `set_aside`: e.g., "Total Small Business".
    - `solicitation_date`: Posted date.
    - `quotes_due_date`: Official deadline.
    - `naics_code`: 6-digit code.
    - `size_standard`: e.g., "500 employees".
    - `dpas_rating`: e.g., "DO-A3" or "NONE".
4.  **item_details**:
    - `product_name`: Primary item.
    - `manufacturer_cage`: 5-char code.
    - `manufacturer_part_number`: Alphanumeric.
    - `nsn`: National Stock Number (13 digits).
    - `technical_description`: Detailed specs.
    - `tdp_access`: "Export Controlled", "Public", or "Request via SAM".
5.  **clins**: List of {{ "clin_num", "description", "quantity", "unit", "contract_type", "inspection_acceptance", "packaging", "notes" }}.
6.  **inspection_testing**:
    - `point`: "Origin" or "Destination".
    - `acceptance_point`: "Origin" or "Destination".
    - `agency`: e.g., "DCMA".
    - `ipi_required`: Boolean (Intial Production Inspection).
    - `quality_standard`: e.g., "ISO 9001".
7.  **delivery_requirements**:
    - `fob_point`: "Origin" or "Destination".
    - `ship_to_address`: Full receiver address.
    - `schedule_aro`: Specific days (e.g., "120 Days ARO").
    - `frequency`: e.g., "Monthly" or "One-time".
    - `acceleration_allowed`: Boolean.
8.  **packaging_requirements**:
    - `preservation_level`: e.g., "Military Level B".
    - `quantity_per_unit`: e.g., "1 per box".
    - `spi_reference`: Specific item number/rev.
    - `labeling_requirements`: e.g., "MIL-STD-129".
9.  **compliance**:
    - `jcp_certification`: Boolean.
    - `itar_controlled`: Boolean.
    - `dd2345_required`: Boolean.
10. **submission_details**:
    - `method`: "Email", "Postal", or "Portal".
    - `email`: Contact email for quotes.
    - `subject_line_format`: Specific requirement.
11. **summary_requirements**: A list of 10 key responsibilities or capabilities required.

Return ONLY valid JSON. Use "Information not provided in solicitation" for missing fields.
"""

SERVICE_EXTRACTION_PROMPT = """
Perform an EXHAUSTIVE extraction for this SERVICE solicitation. 
Follow the Zero-Placeholder policy strictly.

DOCUMENT TEXT:
{document_text}

REQUIRED JSON STRUCTURE:
1.  **notice_id**: Exact character match.
2.  **title**: Full project title.
3.  **general_overview**:
    - `agency`: Full name.
    - `agency_district`: e.g., "Philadelphia District".
    - `location_summary`: States/Counties.
    - `duration`: Performance period (dates).
    - `contract_type`: e.g., "FFP Multi-Year".
    - `set_aside`: Set-aside type.
4.  **scope_of_work**:
    - `task_descriptions`: Detailed list of tasks.
    - `geographic_coverage`: Specific work sites or acreage.
    - `base_clins_summary`: Summary of base requirements.
    - `option_clins_summary`: Summary of optional years.
5.  **key_requirements**:
    - `security_vetting`: Base access/clearance rules.
    - `wage_labor_compliance`: SCA/Davis-Bacon WD numbers.
    - `wage_rates_highlights`: Key labor categories and hourly rates.
    - `insurance_requirements`: {{ "general_liability": "$...", "auto": "$...", "workers_comp": "$..." }}.
    - `veteran_hiring`: Incentives or requirements mentioned.
6.  **legal_clauses**:
    - `subcontracting_limits`: e.g., "50% self-performance".
    - `prohibited_technologies`: Specific bans (Kaspersky, Huawei, TikTok).
    - `far_dfars_highlights`: Critical clauses IDs.
7.  **submission_instructions**:
    - `official_deadline`: Date and time.
    - `delivery_options`: "Hand-carry", "Email", etc.
    - `required_documents`: Checklist of SF1449, Bid Bond, Past Performance, etc.
8.  **post_award**:
    - `self_performance_breakdown`: Logic for hours/pricing.
    - `documentation_maintenance`: Daily logs, etc.
    - `invoice_process`: IPP/WAWF details.
9.  **contacts**:
    - `contracting_officer`: Name/Email/Phone.
    - `bid_inquiries`: Deadline and system (e.g., ProjNet).
    - `reference_websites`: Links to maps, etc.
10. **project_recap**: {{ "performance_period", "work_includes", "pricing_format" }}.
11. **clins_breakdown**: List of {{ "year", "clin_num", "description", "quantity", "unit" }}.
12. **key_dates_actions**: List of {{ "action", "deadline", "reference_doc" }}.

Return ONLY valid JSON. Use "Information not provided in solicitation" for missing fields.
"""

ATTACHMENT_DEEP_DIVE_PROMPT = """
You are analyzing a specific attachment: {filename} ({document_type}).
This document may contain critical granular details missing from the main solicitation.

CONTENT:
{content}

EXTRACT THE FOLLOWING SPECIFIC DETAILS (If present):
1.  **delivery_schedule**: Look for "Delivery Schedule", "Period of Performance", "Time of Delivery", "PoP". Extract specific days (e.g., "120 Days ARO") or Date Range.
2.  **ship_to_address**: Look for "Ship To", "Consignee", "FOB Destination". Extract the full address.
3.  **specifications**: Detailed technical specs, material requirements, or dimensions.
4.  **inspection_terms**: "Inspection at Source" vs "Destination".
5.  **packaging_level**: e.g., "Mil-Std-2073", "Level A/B".

Return a JSON object with these keys. If a field is not found in this specific document, omit it or set to null. DO NOT guess.
"""

VERIFICATION_PROMPT = """
You are a Data Quality Auditor for a {category} solicitation. 
The previous extraction attempt contained errors or placeholders.
Find the MISSING or "Information not provided in solicitation" values in the source text below.

CURRENT DATA:
{extracted_data}

SOURCE DOCUMENT:
{document_text}

INSTRUCTIONS:
1. Locate actual values for fields marked as "Information not provided in solicitation" or placeholders.
2. Return a JSON object with ONLY the corrected fields.
3. If truly missing, use "Explicitly Not Provided".
"""

# Kept for backward compatibility or targeted retry
PRIMARY_EXTRACTION_PROMPT = PRODUCT_EXTRACTION_PROMPT 

TARGETED_CLIN_PROMPT = """
Scan the text Specifically for a "Schedule of Supplies", "Price Schedule", or "CLIN Structure" table.
Extract a list of CLIN objects.
Return JSON list: {{ "clins": [...] }}
"""

TARGETED_ADDRESS_PROMPT = """
Scan the text for "Ship To", "Consignee", "Delivery Point", or "Place of Performance".
Return JSON: {{ "address": "Full Address String" }}
"""
