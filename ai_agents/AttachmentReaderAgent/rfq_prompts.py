"""
RFQ Generation Prompts - Template-Exact Version
Produces output matching Claude Service List.odt and Claude Vendor List.odt EXACTLY
"""

COMMON_RULES = """
# CRITICAL GENERATION RULES - STRICT ADHERENCE REQUIRED

1. **NO BOLD TEXT**: Do NOT use `**` or `__` anywhere in the document.
2. **NO HTML**: Do NOT use HTML comments `<!-- -->` or tags `<>`.
3. **EMAIL POLICY**: The ONLY email allowed is `john@campsable.com`. Remove ALL government emails (.gov, .mil, etc.).
4. **PLACEHOLDER LIMIT**: Use "Details not provided in solicitation documents" AT MOST twice. If information is missing, infer "Not specified" or leave blank if appropriate for the field.
5. **VERBATIM TECHNICAL SPECS**: Extract technical specifications (dimensions, materials, standards) EXACTLY as written. Do not paraphrase.
6. **EMOJI HEADERS**: Use `🏛️` for main sections and `🟩` for summary sections.
7. **DATE FORMAT**: All dates must be `Month DD, YYYY` (e.g., January 01, 2026).
8. **DESCRIPTION AS SOURCE**: If formal attachments (PWS/SOW) are missing, you MUST extract detailed requirements, courses, or scope items directly from the provided description text. Do not just say "Not provided" if the description lists items.
"""

PRODUCT_RFQ_PROMPT = COMMON_RULES + """
## PRODUCT RFQ TEMPLATE INSTRUCTIONS

Generate a markdown RFQ for a **PRODUCT** solicitation.
You MUST follow the structure of the "Claude Vendor List.odt" template EXACTLY.

### INPUT DATA
- **Gov Deadline**: {government_deadline}
- **Camp Sable Deadline**: {CAMP_SABLE_DEADLINE} (Must be used in "Quotes Due")
- **Extracted Content**:
{content_text}

### OUTPUT FORMAT
Generate the following Markdown structure properties:
```markdown
---

Notice ID: {solicitation_number}

### {project_title_all_caps}

Dear [Vendor]:

We are writing to request a formal quote for {product_name}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

Your response is needed on or before {CAMP_SABLE_DEADLINE} in order for us to submit your bid.

There are other documents that I can send you, if this is a project that you would be interested in bidding. If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

[My signature info]

---

## 🏛️ Overview

Agency Issuing RFQ:
{agency_name}
{agency_address_line_1}
{agency_address_line_2}
{agency_state_zip}

Type of Contract: {contract_type}
Set-Aside Type: {set_aside_type}
Solicitation Date: {solicitation_date}
Quotes Due: {CAMP_SABLE_DEADLINE}

Solicitation Title: {project_title}
Contract Number (if awarded): {solicitation_number}
NAICS Code: {naics_code} -- {naics_description}
Size Standard: {size_standard}
DPAS Rating: {dpas_rating}

---

## 🏛️ Items Required

### Item Requested: {product_name}

Manufacturer CAGE: {cage_code}
Manufacturer Part Number: {part_number}

Description: {verbatim_technical_description}

Manufacturer: {manufacturer_name}

---

## CLIN Table

| CLIN | Description | Quantity | Contract Type | Inspection | Packaging | Notes |
|------|-------------|----------|---------------|------------|-----------|-------|
| {clin_number} | {clin_description_with_part_number} | {quantity} {unit} | {contract_type} | {inspection_code} | {packaging_code} | {notes} |

Total Contract Quantity Range:

- Guaranteed Minimum {base_year}-Year Quantity (GMQ): {guaranteed_min} Units
- Maximum {base_year}-Year Contract Quantity: {max_quantity} Units

Packaging:

- {packaging_requirement_1}
- Preservation: {preservation_method}
- Quantity per Unit: {qty_per_unit}
- SPI Reference: {spi_reference}

---

## 🏛️ Inspection & Testing

- Inspection Point: {inspection_point}
- Acceptance Point: {acceptance_point}
- Inspection Agency: {inspection_agency}
- Requirement: {inspection_requirement_summary}

Quality Standard: {quality_standard}
Destructive Testing: {destructive_testing_req}

---

## 🏛️ Delivery Requirements

### General Delivery Terms

- FOB Point: {fob_point}
- Destination: Ship to {ship_to_dodaac}
  - {ship_to_address_line_1}
  - {ship_to_address_line_2}
  - {ship_to_city_state_zip}
  - {ship_to_country}

- Inspection: {inspection_location}
- Acceptance: {acceptance_location}

### Delivery Schedule

- Production delivery: {production_delivery_terms}
- Delivery frequency: {delivery_frequency}
- Acceleration: {acceleration_clause}

Definition:
"Days" means {calendar_or_business} days after {trigger_event}.

Estimated Overall Duration:
This is a {duration_years} contract with {option_years} option years.

---

## 🏛️ Data & Access Requirements

- Technical Data Package (TDP) available via {tdp_access_method}

---

## 🏛️ REQUIRED CERTIFICATIONS & COMPLIANCE

- {certification_1}
- {certification_2}

---

## 🏛️ Submission Details

Quote Submission:
Email proposal (PDF preferred) to john@campsable.com
Subject line: Proposal Submission {solicitation_number} ([company_name])

Due Date: {CAMP_SABLE_DEADLINE}

Evaluation Basis:
- {evaluation_criteria_summary}

---

## 🏛️ Delivery Summary Table

| CLIN | Item | Quantity | Delivery Timeline | Frequency | Inspection | Ship-To | Notes |
|------|------|----------|-------------------|-----------|------------|---------|-------|
| {clin_number} | {clin_description} | {quantity} | {delivery_timeline} | {frequency} | {inspection_code} | {ship_to_city_state} | {key_notes} |

---

## 🟩 Summary of What They Require

In Plain Terms:

- Supply {product_name_summary} built to {key_spec_1}, {key_spec_2}
- Meet {key_standard}
- Inspect and accept at {inspection_loc}, coordinate with {agency_short}
- Deliver to {delivery_location} FOB {fob_type}
- Lead time: {lead_time}
- {other_requirement_summary}
- Participate in {program_name_if_any}
- Follow special packaging per {packaging_std}
- Maintain {quality_system_req}

---

## 🟩 Key Takeaways for Bidders

1. Item supplied: {product_summary}
2. Quality standard: {quality_std_summary}
3. Inspection/acceptance: {inspect_accept_summary}
4. Delivery terms: {delivery_terms_summary}
5. Lead time: {lead_time_summary}
6. Contract duration: {contract_duration_summary}
7. Systems: {systems_summary}
8. Packaging: {packaging_summary}
9. Documentation: {doc_summary}
10. Certifications: {certs_summary}
11. Submission deadline: {CAMP_SABLE_DEADLINE} to john@campsable.com

---

END OF RFQ
```
"""

SERVICE_RFQ_PROMPT = COMMON_RULES + """
## SERVICE RFQ TEMPLATE INSTRUCTIONS

Generate a markdown RFQ for a **SERVICE** solicitation.
You MUST follow the structure of the "Claude Services List.odt" template EXACTLY.

**CRITICAL RULE FOR SERVICE RFQS**: In the "Key Takeaways for Bidder" section at the end, you MUST use the checkbox format `- [ ]` for each item. Do not use numbered lists.

### INPUT DATA
- **Gov Deadline**: {government_deadline}
- **Camp Sable Deadline**: {CAMP_SABLE_DEADLINE} (Must be used in "Quotes Due")
- **Extracted Content**:
{content_text}

### OUTPUT FORMAT
Generate the following Markdown structure properties:
```markdown
# {PROJECT_TITLE_ALL_CAPS}

Notice ID: {solicitation_number}

Dear [Vendor]:

We are writing to request a formal quote for {service_type}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

Your response is needed on or before {CAMP_SABLE_DEADLINE} in order for us to submit your bid.

There are other documents that I can send you, if this is a project that you would be interested in bidding. If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

[My signature info]

---

## 🟩 In Summary

- They want: {scope_summary}
- Time frame: {period_of_performance_summary}
- Delivery locations: {location_summary}

---

## 🏛️ Summary of Project

Title: {project_title}
Type: {contract_type}
Purpose: {project_purpose}
Location:
- {location_list}

Total Work Area:
- Base Contract: {base_scope}
- Option 1: {option_scope}

Project Objective:
{obejctive_summary}

---

## 🏛️ What They Want (Scope of Work)

| Category | Main Tasks |
|----------|------------|
| {category_1} | {tasks_1} |
| {category_2} | {tasks_2} |

---

## 🏛️ Timeline / Period of Performance

| Year/Phase | Dates | Requirements |
|------------|-------|--------------|
| Year 1 | {start_date_1} → {end_date_1} | {reqs_1} |
| Year 2 | {start_date_2} → {end_date_2} | {reqs_2} |

Option 1 (if exercised): {option_1_details}

---

## 🏛️ Deliverables & Reporting Deadlines

- Initial Submittals: {initial_submittals}
- Monthly: {monthly_reports}
- Annually: {annual_reports}
- Final: {final_deliverables}

---

## 🏛️ Delivery / Work Locations

Work occurs across {num_sites} sites:

{state_name} Sites:
- {site_list}

General Delivery/Access:
- {access_reqs}
- {coord_reqs}

---

## 🏛️ Key Compliance Points

- Use {equipment_reqs}
- Meet {safety_reqs}
- {licensing_reqs}
- {env_compliance}
- {quality_control}
- Wage Determination: {wage_determination_info}
- Insurance Requirements: {insurance_reqs}

---

## 🏛️ Acceptance Criteria

To be accepted, each site must:

- {criterion_1}
- {criterion_2}
- Pass final walkthrough - deficiencies corrected at contractor expense
- {other_criteria}

---

## 🏛️ General Overview

- Project Name: {project_name}
- Solicitation Number: {solicitation_number}
- Agency: {agency_name} -- {sub_agency}
- Delivery Period: {period_of_performance_dates}
- Location: {location_summary}
- Type: {contract_type}
- Set-Aside: {set_aside_type}

---

## 🏛️ KeyRequirements

### Certification & Capability
- {cert_reqs}
- {exp_reqs}

### Technical Standards
- {tech_standards}

### Packaging & Labeling (if applicable)
- {packaging_reqs_or_na}

### Wage & Labor Compliance
- Wage Determination: {wd_info}
- Minimum rates: {rate_info}
- Benefits: {benefit_info}

### Security & Compliance
- {security_reqs}

### Insurance Requirements
- General Liability: {gl_amount}
- Auto Liability: {auto_amount}
- Workers Compensation: {wc_amount}
- Employers Liability: {el_amount}

---

## 🏛️ Bid Submission Instructions

### Submission Method & Contact
- Format: Email
- Recipient: john@campsable.com
- Subject line: Quote for {solicitation_number} {project_name}
- Deadline: {CAMP_SABLE_DEADLINE}

### Required Quote Content
1. {req_1}
2. {req_2}
3. {req_3}
4. {req_4}
5. {req_5}
6. {req_6}

### Evaluation Criteria
- Award basis: {award_basis}
- Evaluation factors: {eval_factors}
- {special_factors}

---

## 🏛️ Base Contract Scope

| CLIN | Item Description | Quantity | Unit | Notes |
|------|------------------|----------|------|-------|
| {clin_id} | {clin_desc} | {clin_qty} | {clin_unit} | {clin_notes} |

Total Base Contract Price for {base_desc}

---

## 🏛️ Option 1 Scope

| CLIN | Item Description | Quantity | Unit | Notes |
|------|------------------|----------|------|-------|
| {opt_clin_id} | {opt_clin_desc} | {opt_clin_qty} | {opt_clin_unit} | {opt_clin_notes} |

Total Option 1 Price for {opt_desc} (if exercised)

---

## 🏛️ ATTACHMENTS PROVIDED

- {attachment_list}

---

## 🟩 Summary for Bidders

1. {summary_point_1}
2. {summary_point_2}
3. {summary_point_3}
4. {summary_point_4}
5. {summary_point_5}
6. {summary_point_6}
7. {summary_point_7}
8. {summary_point_8}

---

## 🟩 Key Takeaways for Bidder

- [ ] {takeaway_1}
- [ ] {takeaway_2}
- [ ] {takeaway_3}
- [ ] {takeaway_4}
- [ ] {takeaway_5}
- [ ] {takeaway_6}
- [ ] {takeaway_7}
- [ ] {takeaway_8}
- [ ] {takeaway_9}
- [ ] {takeaway_10}

---

END OF RFQ
```
"""
