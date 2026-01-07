"""
RFQ Generation Prompts - Template-Exact Version
Produces output matching Claude Service List.odt and Claude Vendor List.odt EXACTLY
"""

COMMON_RULES = """
## CRITICAL: 100% Template Fidelity Required

You are generating an RFQ that MUST match the user's reference templates EXACTLY.

### NON-NEGOTIABLE RULES:
1. NO bold formatting using ** anywhere (use plain text)
2. ONLY john@campsable.com as contact email (never government contacts)
3. ONLY Camp Sable deadline = Government deadline - 4 business days
4. ALL information must be extracted from solicitation (no placeholders)
5. Professional greeting: "Dear [Vendor]:" at start
6. Professional closing with signature placeholder
7. Emoji section headers (🏛️ for sections, 🟩 for summaries)
8. Markdown tables with proper pipe format | Header | Header |
9. Horizontal rules (---) between major sections

### EXTRACTION PRIORITY:
- Process EVERY attachment file provided
- Extract ALL line items, CLINs, quantities, specifications
- Extract complete addresses (all lines, ZIP codes)
- Extract exact dates (never "as required" or "per solicitation")
- Extract all technical specifications verbatim
- If data truly missing, write "Not specified in solicitation"
"""

PRODUCT_RFQ_PROMPT = COMMON_RULES + """
## PRODUCT RFQ TEMPLATE

Generate a product RFQ matching this EXACT structure:

---

Notice ID: {notice_id}

### {TITLE IN ALL CAPS}

Dear [Vendor]:

We are writing to request a formal quote for {brief item description}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

Your response is needed on or before {CAMP_SABLE_DEADLINE} in order for us to submit your bid.

There are other documents that I can send you, if this is a project that you would be interested in bidding. If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

[My signature info]

---

## 🏛️ Overview

Agency Issuing RFQ:
{Agency Name}
{Complete Address Line 1}
{Complete Address Line 2}
{City, State ZIP+4}

Type of Contract: {contract_type}
Set-Aside Type: {set_aside}
Solicitation Date: {published_date}
Quotes Due: {CAMP_SABLE_DEADLINE}

Solicitation Title: {full_title}
Contract Number (if awarded): {solicitation_number}
NAICS Code: {naics} -- {naics_description}
Size Standard: {size_standard}
DPAS Rating: {dpas_rating}

---

## 🏛️ Items Required

### Item Requested: {item_name_from_solicitation}

Manufacturer CAGE: {cage_code}
Manufacturer Part Number: {part_number}

Description: {technical_description}

{ANY_ADDITIONAL_ITEM_CONTEXT}

---

## CLIN Table

| CLIN | Description | Quantity | Contract Type | Inspection | Packaging | Notes |
|------|-------------|----------|---------------|------------|-----------|-------|
| {clin_1} | {description} | {qty} {unit} | {type} | {inspection} | {packaging} | {notes} |
| {clin_2} | {description} | {qty} {unit} | {type} | {inspection} | {packaging} | {notes} |

Total Contract Quantity Range:

- Guaranteed Minimum {period}-Year Quantity (GMQ): {min_qty} {unit}
- Maximum {period}-Year Contract Quantity: {max_qty} {unit}

Packaging:

- {packaging_standard}
- Preservation: {preservation_level}
- Quantity per Unit: {qty_per_unit}
- SPI Reference: {spi_reference}

---

## 🏛️ Inspection & Testing

- Inspection Point: {inspection_point}
- Acceptance Point: {acceptance_point}
- Inspection Agency: {inspection_agency}
- Requirement: {inspection_requirements}

{IF_FAT_REQUIRED}
First Article Testing (FAT):
- Required: {number} units from first production lot
- Verified by: {verification_agency}
- Approval required before full production

Quality Standard: {quality_standard}
Destructive Testing: {destructive_testing_note}

---

## 🏛️ Delivery Requirements

### General Delivery Terms

- FOB Point: {fob_point}
- Destination: Ship to {destination_name}
  - {address_line_1}
  - {address_line_2}
  - {city_state_zip}
  - {special_instructions}

- Inspection: {inspection_location}
- Acceptance: {acceptance_location}

### Delivery Schedule

- {IF_FAT} FAT delivery: {fat_timeline}
- Production delivery: {production_timeline}
- Delivery frequency: {delivery_frequency}
- Acceleration: {acceleration_policy}

Definition:
"Days" means {calendar_or_business} days after {trigger_event}.

Estimated Overall Duration:
This is a {contract_duration} with {options_description}.

---

## 🏛️ Data & Access Requirements

- Technical Data Package (TDP) available via {source}
- {IF_RESTRICTED} Suppliers must have current {certification_required}
- {IF_ITAR} Follow ITAR/export-controlled document handling procedures

---

## 🏛️ REQUIRED CERTIFICATIONS & COMPLIANCE

- ISO 9001:2015 or equivalent
- {IF_NADCAP} NADCAP certification for {processes}
- {IF_CALIBRATION} Calibration per {standard}
- {IF_ITAR} ITAR / JCP certification
- {IF_CMMC} CMMC Level {level} {certification_type}

---

## 🏛️ Submission Details

Quote Submission:
Email proposal (PDF preferred) to john@campsable.com
Subject line: Proposal Submission {solicitation_number} ({company_name})

Due Date: {CAMP_SABLE_DEADLINE}

Evaluation Basis:
- {evaluation_basis}
- {IF_ALL_OR_NONE} "All or None" clause applies - partial bids not accepted

{IF_CONTACT_PROVIDED}
Inspection Contact:
{contact_name}
Phone: {phone}
Email: {email}

---

## 🏛️ Delivery Summary Table

| CLIN | Item | Quantity | Delivery Timeline | Frequency | Inspection | Ship-To | Notes |
|------|------|----------|-------------------|-----------|------------|---------|-------|
| {clin} | {item} | {qty} {unit} | {timeline} | {frequency} | {inspection} | {location} | {notes} |

---

## 🟩 Summary of What They Require

In Plain Terms:

- Supply {item_description} built to {specifications}
- Meet {quality_standards}
- Inspect and accept at {inspection_location}, coordinate with {agency}
- Deliver to {delivery_location} FOB {fob_terms}
- Lead time: {lead_time_summary}
- {contract_duration_summary}
- Participate in {systems_required}
- Follow special packaging per {packaging_standards}
- Maintain {documentation_requirements}
- {IF_JCP} Possess approved {certifications_required}

---

## 🟩 Key Takeaways for Bidders

1. Item supplied: {exact_part_number_and_description}
2. Quality standard: {quality_requirements}
3. Inspection/acceptance: {inspection_summary}
4. Delivery terms: {delivery_summary}
5. Lead time: {lead_time}
6. Contract duration: {duration_and_options}
7. Systems: {electronic_systems_required}
8. Packaging: {packaging_summary}
9. Documentation: {document_requirements}
10. Certifications: {certifications_list}
11. {IF_ALL_OR_NONE} All or None clause applies
12. Submission deadline: {CAMP_SABLE_DEADLINE} to john@campsable.com

---

END OF RFQ

---

## GENERATION INSTRUCTIONS:

1. Extract ALL information from the solicitation attachments
2. Calculate Camp Sable deadline: Government deadline - 4 business days (skip weekends)
3. Fill EVERY placeholder with actual data from solicitation
4. If data is missing, write "Not specified in solicitation"
5. NEVER use bold formatting (**)
6. NEVER show government contact info or deadlines
7. Use ONLY john@campsable.com
8. Include ALL CLINs from original
9. Build complete tables with all columns
10. Verify every section is present before output
"""

SERVICE_RFQ_PROMPT = COMMON_RULES + """
## SERVICE RFQ TEMPLATE

Generate a service RFQ matching this EXACT structure:

---

# {PROJECT TITLE IN ALL CAPS}

Notice ID: {notice_id}

Dear [Vendor]:

We are writing to request a formal quote for {service_type}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

Your response is needed on or before {CAMP_SABLE_DEADLINE} in order for us to submit your bid.

There are other documents that I can send you, if this is a project that you would be interested in bidding. If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

[My signature info]

---

## 🟩 In Summary

- They want: {scope_summary_with_specific_quantities_and_timeframe}
- Time frame: {contract_duration}
- Delivery locations: {specific_locations_list}

---

## 🏛️ Summary of Project

Title: {full_project_title}
Type: {contract_type}
Purpose: {project_purpose_detailed}
Location:
- {location_1}
- {location_2}

Total Work Area:
- Base Contract: {base_acreage_or_scope}
- Option 1: {option_acreage_or_scope}

Project Objective:
{detailed_objective_from_solicitation}

---

## 🏛️ What They Want (Scope of Work)

| Category | Main Tasks |
|----------|------------|
| {category_1} | {detailed_tasks_and_deliverables} |
| {category_2} | {detailed_tasks_and_deliverables} |
| {category_3} | {detailed_tasks_and_deliverables} |

---

## 🏛️ Timeline / Period of Performance

| Year/Phase | Dates | Requirements |
|------------|-------|--------------|
| Year 1 | {start_date} → {end_date} | {all_activities_for_year_1} |
| Year 2 | {start_date} → {end_date} | {all_activities_for_year_2} |
| Year 3 | {start_date} → {end_date} | {all_activities_for_year_3} |

{IF_OPTIONS}
Option 1 (if exercised): {option_details}

---

## 🏛️ Deliverables & Reporting Deadlines

- Initial Submittals: {list_all_required_submittals_with_deadlines}
- Monthly: {monthly_reporting_requirements}
- Annually: {annual_reporting_requirements}
- Final: {final_deliverables_and_acceptance_criteria}

---

## 🏛️ Delivery / Work Locations

Work occurs across {number} sites:

{STATE_1} Sites:
- {site_list_with_details}

{STATE_2} Sites:
- {site_list_with_details}

General Delivery/Access:
- {access_details}
- {coordination_requirements}

---

## 🏛️ Key Compliance Points

- Use {systems_required}
- Meet {safety_standards}
- {licensing_requirements}
- {environmental_compliance}
- {quality_control_requirements}
- {wage_determination_applicability}
- {insurance_requirements}

---

## 🏛️ Acceptance Criteria

To be accepted, each site must:

- {acceptance_criterion_1}
- {acceptance_criterion_2}
- {acceptance_criterion_3}
- Pass final walkthrough - deficiencies corrected at contractor expense
- {additional_requirements}

---

## 🏛️ General Overview

- Project Name: {project_name}
- Solicitation Number: {solicitation_number}
- Agency: {agency_name} -- {sub_agency}
- Delivery Period: {start_date} -- {end_date}
- Location: {locations}
- Type: {contract_type}
- Set-Aside: {set_aside_type}

---

## 🏛️ Key Requirements

### Certification & Capability
- {required_certifications}
- {license_requirements}
- {experience_requirements}

### Technical Standards
- {technical_standards}
- {specifications}
- {service_standards}

### Packaging & Labeling (if applicable)
- {packaging_standards}
- {labeling_requirements}

### Wage & Labor Compliance
- Wage Determination: {wd_number_and_details}
- Minimum rates: {rate_summary}
- Benefits: {benefits_requirements}

### Security & Compliance
- {security_requirements}
- {government_compliance}
- {far_dfars_requirements}

### Insurance Requirements
- General Liability: {amount}
- Auto Liability: {amount}
- Workers Compensation: {amount}
- Employers Liability: {amount}

---

## 🏛️ Bid Submission Instructions

### Submission Method & Contact
- Format: {email_or_other}
- Recipient: john@campsable.com
- Subject line: {subject_format}
- Deadline: {CAMP_SABLE_DEADLINE}

### Required Quote Content
1. {requirement_1}
2. {requirement_2}
3. {requirement_3}
4. {requirement_4}
5. {requirement_5}
6. {requirement_6}

### Evaluation Criteria
- Award basis: {evaluation_basis}
- Evaluation factors: {factors}
- {special_considerations}

---

## 🏛️ Base Contract Scope

| CLIN | Item Description | Quantity | Unit | Notes |
|------|------------------|----------|------|-------|
| {clin} | {description} | {qty} | {unit} | {notes} |

Total Base Contract Price for {description_summary}

---

## 🏛️ Option 1 Scope

{IF_OPTIONS_EXIST}
| CLIN | Item Description | Quantity | Unit | Notes |
|------|------------------|----------|------|-------|
| {clin} | {description} | {qty} | {unit} | {notes} |

{IF_NO_OPTIONS}
Not Included in This Solicitation - This is a {duration} contract with no option periods.

---

## 🏛️ ATTACHMENTS PROVIDED

- {attachment_1_name}: {1_sentence_description}
- {attachment_2_name}: {1_sentence_description}
- {attachment_3_name}: {1_sentence_description}

---

## 🟩 Summary for Bidders

1. {detailed_what_must_perform}
2. {standards_compliance_required}
3. {key_deliverables}
4. {timelines}
5. {work_locations}
6. {quality_performance_standards}
7. {wage_compliance}
8. {submission_deadline_and_method}

---

## 🟩 Key Takeaways for Bidder

- [ ] {requirement_1}
- [ ] {requirement_2}
- [ ] {requirement_3}
- [ ] {requirement_4}
- [ ] {requirement_5}
- [ ] {requirement_6}
- [ ] {requirement_7}
- [ ] {requirement_8}
- [ ] {requirement_9}
- [ ] {requirement_10}
- [ ] {requirement_11}
- [ ] {requirement_12}

---

END OF RFQ

---

## GENERATION INSTRUCTIONS:

1. Extract ALL information from PWS/SOW attachments
2. Calculate Camp Sable deadline: Government deadline - 4 business days (skip weekends)
3. Fill EVERY placeholder with actual data from solicitation
4. Build complete tables with all rows/columns
5. NEVER use bold formatting (**)
6. NEVER show government contact info or deadlines
7. Use ONLY john@campsable.com
8. Include "In Summary" section at TOP with exactly 3 bullets
9. Use checklist format (- [ ]) for Key Takeaways
10. List ALL attachments with descriptions
"""
