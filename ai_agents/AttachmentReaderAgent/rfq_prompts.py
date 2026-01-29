"""
RFQ Generation Prompts - 100% Information Extraction
Matches Claude Vendor List.odt and Claude Service List.odt EXACTLY
"""

EXTRACTION_RULES = """
# COMPREHENSIVE EXTRACTION METHODOLOGY

## EXTRACTION PRIORITY ORDER

### Level 1: Direct Extraction (Highest Priority)
Extract information EXACTLY as written in documents:
- Technical specifications (part numbers, NSN, CAGE, model numbers)
- Measurements and dimensions (with units)
- Standards and references (MIL-STD-2073-1, ISO 9001:2015, etc.)
- Dates and deadlines
- Addresses (street, city, state, zip)
- Quantities with units
- Contact names and titles
- CLIN details (number, description, quantity, unit)

### Level 2: Cross-Document Synthesis
When information is scattered across multiple documents:
- Combine data from main page + attachments
- Use SF 1449 data as authoritative source
- Cross-reference PWS/SOW with CLIN structure
- Validate dates across multiple mentions
- Verify addresses in multiple locations

### Level 3: Intelligent Inference (Only When Necessary)
When data is genuinely missing, infer using:
- Industry standards for the type of contract
- Similar requirements in related sections
- NAICS code typical requirements
- Agency standard practices

### Level 4: Professional Defaults (Last Resort)
Use professional defaults only when all else fails:
- "Firm Fixed Price" for contract type
- "Destination" for FOB/Inspection
- "ISO 9001:2015" for quality standards
- "Full and Open Competition" for set-aside

## DOCUMENT READING STRATEGY

### Step 1: Initial Survey (2 minutes)
- Identify document types (solicitation, PWS, SF 1449, wage determination, etc.)
- Note number of CLINs/line items
- Identify if PRODUCT or SERVICE
- Find key reference documents

### Step 2: Systematic Extraction (Main Pass)
Read in this order:
1. Main solicitation description (overview, dates, contacts)
2. SF 1449 or equivalent (CLINs, quantities, addresses)
3. PWS/SOW (scope, deliverables, standards)
4. Technical specifications/drawings (parts, dimensions)
5. Wage determinations (if SERVICE)
6. All other attachments (insurance, certifications, maps)

### Step 3: Gap Analysis
After main pass, identify missing:
- Delivery address (if not found, use agency address)
- NAICS size standard (look up standard for that NAICS)
- Insurance amounts (check FAR clauses)
- Wage rates (look for WD attachments)
- Certifications (check evaluation criteria)

### Step 4: Quality Validation
Before finalizing:
- No placeholder text like "Extract from..." or "[Extract...]"
- No instruction leakage from prompts
- All sections complete
- Tables properly formatted
- Professional tone throughout

## FIELD-SPECIFIC EXTRACTION RULES

### Agency Information
**Sources:** Header, footer, "Contracting Office" section, point of contact
**Must Extract:**
- Full legal agency name (not abbreviation only)
- Complete street address
- City, State, ZIP (with +4 if available)
**Format:** 
```
U.S. Army Corps of Engineers
332 Minnesota Street, Suite E1500
Saint Paul, MN 55101
```

### Solicitation Numbers
**Sources:** Header, Notice ID, Solicitation Number field
**Format Examples:**
- W912ES26BA007
- SPE4A1-26-R-0123
- ASR-8-2026-000580-A
**Never Use:** Generic IDs, document titles, or placeholder text

### NAICS Codes
**Sources:** Main page, SF 1449, set-aside section
**Must Extract:**
- 6-digit code
- Industry description
- Size standard (employees or revenue)
**Example:** 335314 -- Relay and Industrial Control Manufacturing, 600 employees

### Dates and Deadlines
**Parse These Formats:**
- January 28, 2025
- Jan 28, 2025
- 01/28/2025
- 2025-01-28
- 28 Jan 25

**CRITICAL: Convert ALL dates to this format in output:** Month DD, YYYY (e.g., "January 13, 2026")

**Calculate Camp Sable Deadline:**
Government deadline - 4 BUSINESS days (skip Saturday and Sunday)
Example: Gov deadline Tuesday Jan 28 → Camp Sable Friday Jan 24

**ABSOLUTE REQUIREMENT - Date Consistency:** 
- ALL date references throughout the entire RFQ must use identical "Month DD, YYYY" format
- Response deadline, submission deadline, quotes due, and all other dates MUST match exactly
- Use the CAMP_SABLE_DEADLINE variable consistently - never hardcode different dates

### Delivery Addresses
**Priority Order:**
1. Look for "Ship to" or "Deliver to" section
2. Check SF 1449 delivery address field
3. Look for DODAAC and resolve to address
4. If not found: Use agency address from overview section

**Required Elements:**
- Facility/Building name (if applicable)
- Street address
- City, State ZIP
- Special instructions (if any)

### CLIN Tables (CRITICAL)

**For 1-19 Items:** List each item individually
| **CLIN** | **Description** | **Quantity** | **Contract Type** | **Inspection** | **Packaging** | **Notes** |
|------|-------------|----------|---------------|------------|-----------|-------|
| 0001 | Widget Assembly | 10 | FFP | Origin | Commercial | Base year |

**For 20+ Items:** Create SUMMARY by category (6-10 rows max)
| **CLIN Range** | **Category** | **Item Count** | **Contract Type** | **Inspection** | **Packaging** | **Notes** |
|------------|----------|------------|---------------|------------|-----------|-------|
| 1-15 | Enclosure Components | 15 items | FFP | Destination | Commercial | Housing and panels |
| 16-50 | Electronic Components | 35 items | FFP | Destination | Commercial | PCBs, modules, displays |
| 51-100 | Hardware & Fasteners | 50 items | FFP | Destination | Commercial | Screws, washers, brackets |

**Category Grouping Logic:**
For electronics: Enclosures, Power, Processing, Interface, Hardware, Wire/Cable
For construction: Site prep, Structure, MEP, Finishes, Hardware, Materials
For services: Phase 1 tasks, Phase 2 tasks, Deliverables, Reports, Training

### Technical Specifications (PRODUCT)
**Must Extract Verbatim:**
- Part numbers (exactly as written)
- CAGE codes
- NSN (13-digit format: 1234-56-789-0123)
- Drawing numbers with revision
- Dimensions with units (inches, mm, etc.)
- Materials (stainless steel 18-8, aluminum 6061, etc.)
- Standards (MIL-STD-2073-1, ASTM D1234, etc.)
- Electrical specs (voltage, amperage, phase)

**Example (Correct):**
"Cable Assembly per Drawing 12992465 Rev A, CAGE 19200, NSN 6150-01-501-1062, 24 AWG stranded copper wire, 18 inches length, MIL-STD-2073-1 Level B packaging"

**Example (Wrong - Too Vague):**
"Cable assembly with standard specifications"

### Scope of Work (SERVICE)
**Extract from PWS/SOW:**
- Every major task (do not summarize)
- Deliverable names and due dates
- Performance standards with metrics
- Acceptance criteria (measurable)
- Site locations with addresses
- Equipment requirements
- Personnel qualifications
- Reporting requirements with frequencies

### Wage Determinations (SERVICE)
**Must Extract:**
- WD number (e.g., 2015-4191, WD 22-0345)
- Applicable states
- Job classifications (exact titles)
- Hourly rates (with fringe benefits separated)
- Health & Welfare amounts
- Vacation/Holiday rates

**Example:**
"Wage Determination 2015-4191 (Revision 23) applies to Minnesota and North Dakota.
- Laborer: $28.50/hour + $12.35 H&W
- Equipment Operator: $35.75/hour + $14.20 H&W"

### Insurance Requirements
**Sources:** FAR 52.228-5, Special provisions, Risk management section
**Must Extract:**
- General Liability: $X per occurrence / $Y aggregate
- Auto Liability: $X combined single limit
- Workers Compensation: Statutory requirements for [states]
- Employers Liability: $X per accident

**If Not Specified:** "Insurance requirements to be determined per Task Order" (not just "TBD")

### Certifications & Compliance
**Look for:**
- ISO certifications (9001, 14001, 45001, AS9100)
- ITAR registration
- JCP certification (DD2345)
- Security clearances (Secret, Top Secret)
- CMMC level requirements
- DPAS rating and priority

## QUALITY CONTROL RULES

### Prohibited Text (Never Use)
### Prohibited Text (Never Use)
- "Extract from documents"
- "[Extract exact...]"
- "See attachment" (summarize instead)
- "N/A" (use specific text)
- "TBD" (provide context or "To be determined at Task Order")
- "Various" (unless truly multi-source)
- "Not specified in solicitation documents" (STRICTLY PROHIBITED)
- "Information not provided"

### Maximum Placeholder Usage
- "Not specified": 0 instances allowed. You MUST infer or use a professional default.
- If a delivery schedule is missing: "To be determined at Task Order"
- If a specific standard is missing: "Applicable industry and safety standards"
- If a specific location is missing: "To be coordinated with Contracting Officer Representative (COR)"
- If a date is missing: "To be determined at Task Order"

### Professional Writing Standards
- Complete sentences (no fragments)
- Consistent verb tense
- Active voice preferred
- No promotional language
- Technical accuracy paramount
- Vendor-friendly language

### Parts List & Document Completeness
**CRITICAL REQUIREMENT:** The RFQ must be 100% complete and self-contained.
- Extract ALL CLIN items and include complete details in RFQ body
- **NEVER** use "available upon request", "contact for details", or "see attachments" - ALL information must be in the RFQ body
- If >15 parts, include full table with all items listed
- The RFQ IS the complete package - no external references permitted
- **DO NOT** include any "Note:" lines suggesting information is "available upon request"

**STRICTLY PROHIBITED PHRASES:**
- "available in attached solicitation documents or upon request"
- "available upon request"
- "upon request"
- "other documents available"
- "I can send you"
- "send if interested"
- "contact for more information"
- "additional documents available"
- "refer to solicitation"
- "see attachments"

### Formatting Standards
- No ** bold in body text (EXCEPTION: Table headers MUST be bold for visibility)
- Proper emoji: 🏛️ for sections, 🟩 for summaries
- Tables: Markdown pipe format with proper alignment AND **bold headers**
- Horizontal rules (---) between major sections
- Consistent capitalization
- No HTML artifacts
"""

PRODUCT_RFQ_PROMPT = f"""{EXTRACTION_RULES}

## PRODUCT RFQ TEMPLATE

Generate following this EXACT structure. Every placeholder must be filled with real data.

```markdown
---

Notice ID: [solicitation_number - e.g., ASR-8-2026-000580-A]

### [PRODUCT NAME IN ALL CAPS]

Dear [Vendor]:

We are writing to request a formal quote for [specific_product_name]. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

Your response is needed on or before [CAMP_SABLE_DEADLINE] in order for us to submit your bid.

All requirements, specifications, and compliance criteria are detailed below. Please review the complete RFQ carefully. If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

[My signature info]

---

## 🏛️ Overview

Agency Issuing RFQ:
[Full_Agency_Legal_Name]
[Complete_Street_Address]
[City], [State] [ZIP]

Type of Contract: [Extract or "Firm Fixed Price"]
Set-Aside Type: [Extract or "Full and Open Competition"]
Solicitation Date: [Posted_Date]
Quotes Due: [CAMP_SABLE_DEADLINE]

Solicitation Title: [Full_Official_Title]
Contract Number (if awarded): [Solicitation_Number]
NAICS Code: [6-digit] -- [Industry_Description]
Size Standard: [Employees_or_Revenue from NAICS table]
DPAS Rating: [Extract or "DO-A1"]

---

## 🏛️ Items Required

### Item Requested: [Specific_Product_Name_from_Title]

**EXTRACTION LOGIC FOR THIS SECTION:**

1. **For Single Item:**
Manufacturer CAGE: [Exact_CAGE_Code]
Manufacturer Part Number: [Exact_Part_Number]
Description: [Verbatim_technical_description_from_specifications]

2. **For Kit/Assembly (5-20 items):**
Manufacturer CAGE: [Primary_Manufacturer_CAGE or list top 3]
Manufacturer Part Number: [Assembly_Part_Number or "Multiple - see CLIN table"]
Description: [High-level_kit_description with key components listed]

3. **For Multi-Item Package (20+ items):**
Manufacturer CAGE: Various (multiple manufacturers - see CLIN table)
Manufacturer Part Number: See CLIN Table Below
Description: [Comprehensive_system_description including major subsystems and purpose]
Example: "Complete antenna control box assembly for ASR radar systems. Includes programmable logic controller chassis with I/O modules, power supply system with surge protection, front panel indicators and controls, internal wiring harnesses, and mechanical mounting hardware. System provides automated antenna positioning control and status monitoring per FAA technical specifications."

Manufacturer: [Extract or "Various"]

**NEVER USE:** "Standard commercial specifications apply" unless documents explicitly state this

---

## CLIN Table

## CLIN Table

[INSTRUCTION: Select ONE of the following table formats based on the total line item count. Output ONLY the table, no instruction text.]

[INSTRUCTION: If 1-19 items, use this detailed format with BOLD headers:]
| **CLIN** | **Item Description** | **Quantity** | **Unit** | **Notes** |
|------|------------------|----------|------|-------|
| [CLIN] | [Full_Description] | [Qty] | [Unit] | [Notes_or_"None"] |

[INSTRUCTION: If 20+ items, use this summary format with BOLD headers:]
| **CLIN Range** | **Category** | **Item Count** | **Contract Type** | **Inspection** | **Packaging** | **Notes** |
|------------|----------|------------|---------------|------------|-----------|-------|
| 1-10 | [Category_Name] | 10 items | FFP | Destination | Commercial | [Brief_description_or_"Standard"] |
| [Range] | [Category] | [Count] | FFP | Destination | Commercial | [Description] |

[INSTRUCTION: If Option Periods exist, include this table below the main table with BOLD headers:]

🏛️ Option 1 Scope
| **CLIN** | **Item Description** | **Quantity** | **Unit** | **Notes** |
|------|------------------|----------|------|-------|
| [CLIN] | [Full_Description] | [Qty] | [Unit] | [Option_Period_Details] |

Total Option 1 Price for Supplies and Services (if exercised)

[INSTRUCTION: End tables.]

Total Contract Quantity Range:

- Guaranteed Minimum Quantity (GMQ): [Extract_minimum_qty or "See CLINs above"]
- Maximum Contract Quantity: [Extract_maximum_qty or "See CLINs above"]

Packaging:

- [Extract_standard or "Commercial Packaging per ASTM D3951"]
- Preservation: [Extract_level or "Level A - Minimum Protection"]
- Quantity per Unit: [Extract or "1 per package"]
- SPI Reference: [Extract_SPI_number or "N/A"]

---

## 🏛️ Inspection & Testing

- Inspection Point: [Extract or "Destination"]
- Acceptance Point: [Extract or "Destination"]
- Inspection Agency: [Extract or "Receiving Activity"]
- Requirement: [Extract_specific_requirements or "Visual and functional inspection per contract specifications"]

**EXTRACTION LOGIC:**
- Look for "Inspection and Acceptance" section
- Check for DCMA mentions
- Note FAT (First Article Test) requirements
- Extract testing procedures if specified

**IF First Article Testing Required:**
First Article Testing (FAT):
- Required: [Number] units from first production lot
- Verified by: [DCMA/DCIS/Agency]
- Submit to: [Address]
- Approval timeline: [Days]

Quality Standard: [Extract or "ISO 9001:2015 or equivalent"]
Destructive Testing: [Extract or "Not required"]

---

## 🏛️ Delivery Requirements

### General Delivery Terms

**EXTRACTION LOGIC FOR DELIVERY ADDRESS:**
1. Search documents for: "Ship to", "Deliver to", "Delivery Address", "Destination"
2. Check SF 1449 block for delivery address
3. Look for DODAAC and decode
4. **IF NOT FOUND:** Use the Agency Address from Overview section above

- FOB Point: [Extract or "Destination"]
- Destination: Ship to [Facility_Name_if_applicable]
  - [Complete_Street_Address]
  - [Building/Suite_Number_if_applicable]
  - [City], [State] [ZIP+4]
  - [Special_delivery_instructions_if_any]

- Inspection: [Extract or "Destination"]
- Acceptance: [Extract or "Destination"]

### Delivery Schedule

**EXTRACTION LOGIC:**
- Look for "Delivery Schedule" section
- Check CLIN-specific delivery requirements
- Note ARO (After Receipt of Order) timelines

- **IF FAT Required:** FAT samples due [X] days ARO
- Production delivery: [Timeline - e.g., "120 days ARO" or "30 days after FAT approval"]
- Delivery frequency: [Extract or "Single delivery" or "Monthly shipments of [qty]"]
- Acceleration: [Extract or "Early delivery permitted at no additional cost"]

Definition:
"Days" means [calendar or business] days after [receipt of order or other trigger event].

Estimated Overall Duration:
This is a [X]-year [indefinite quantity or requirements] contract with [Y] option year(s).

---

## 🏛️ Data & Access Requirements

**EXTRACTION LOGIC:**
- Look for TDP (Technical Data Package) references
- Check for ITAR requirements
- Note JCP certification needs
- Find data rights clauses

- Technical Data Package (TDP) available via [SAM.gov_link or "Direct from Contracting Officer"]
- **IF ITAR Controlled:** Contractor must have ITAR registration and comply with export control regulations
- **IF JCP Required:** Current DD2345 certification required to access technical data
- **IF CDRL Required:** List specific Contract Data Requirements List items

---

## 🏛️ REQUIRED CERTIFICATIONS & COMPLIANCE

**EXTRACTION LOGIC:**
- Check evaluation criteria section
- Look for special provisions
- Note FAR/DFARS clauses
- Identify mandatory certifications
- Separate government requirements from Camp Sable requirements

**OUTPUT FORMAT:**

**Government Requirements (from solicitation):**
[List ONLY certifications explicitly required by the government solicitation - extract verbatim]
[Examples: ISO 9001:2015, AS9100, ITAR registration, JCP (DD2345), CMMC Level X, Anti-counterfeit parts program per DFARS 252.246-7007]
[If specific requirements found, list each on separate line without conditional markers]
[If no specific certifications in solicitation, write: "See solicitation documents for specific requirements"]

## 🟩 Camp Sable Qualifications

Camp Sable meets the following government requirements:
- SAM.gov registration (active and current) - Camp Sable provides; government requires
- FAR 52.212-3 Representations and Certifications (complete) - Camp Sable provides; government requires

**Bidder/Vendor Requirements:**
The bidder/vendor must possess:
- ISO 9001:2015 or equivalent quality management system certification

**CRITICAL:** 
- Do NOT include conditional markers like "**IF Defense:**" or "**IF ITAR:**" in the output
- Do NOT add "(This is a Camp Sable requirement.)" labels - they cause confusion
- Only list requirements that actually apply based on the solicitation content

---

## 🏛️ Submission Details

Quote Submission:
Email proposal (PDF preferred) to john@campsable.com
Subject line: Proposal Submission [Solicitation_Number] ([Your_Company_Name])

Due Date: [CAMP_SABLE_DEADLINE]

Evaluation Basis:
- [Extract or "Lowest Price Technically Acceptable (LPTA)"]
- **IF Best Value:** Technical capability ([X]%), Past performance ([Y]%), Price ([Z]%)
- **IF All-or-None:** Partial bids will not be accepted - quote must cover all items

**IF Government Inspection Contact Provided:**
Inspection Coordination:
[Contact_Name], [Title]
Phone: [Number]
Email: [Email]

---

## 🏛️ Delivery Summary Table

**SUMMARY FORMAT (appropriate to item count):**

**IF Few CLINs (1-10):** List each with delivery details

| **CLIN** | **Item** | **Quantity** | **Delivery Timeline** | **Frequency** | **Inspection** | **Ship-To** | **Notes** |
|------|------|----------|-------------------|-----------|------------|---------|-------|
| [CLIN] | [Item] | [Qty] [Unit] | [Timeline] | [Frequency] | [Point] | [Location] | [Notes] |

**IF Many CLINs (20+):** Summarize delivery by category

| **Category** | **Items** | **Total Qty** | **Delivery Start** | **Frequency** | **Inspection** | **Ship-To** | **Notes** |
|----------|-------|-----------|----------------|-----------|------------|---------|-------|
| [Category] | [Count] items | [Total] | [Timeline] | [Frequency] | [Point] | [Location] | [Notes] |

---

## 🟩 Summary of What They Require

In Plain Terms:

**WRITE 8-12 COMPLETE BULLET POINTS - NOT FRAGMENTS:**

- Supply [specific_item_with_details] conforming to [standards]
- Meet [specific_quality_standards] with [certification_requirements]
- Inspect and accept at [specific_location], coordinate with [agency/office]
- Deliver to [complete_address] FOB [terms]
- Lead time: [specific_timeline] after [trigger_event]
- Contract structure: [duration] with [options_details]
- Participate in [specific_electronic_systems - WAWF, PIEE, etc.]
- Follow packaging requirements per [specific_standard - MIL-STD-2073-1, etc.]
- Maintain [specific_documentation] for [timeframe]
- **IF JCP:** Possess approved [certification_type] to access restricted technical data
- **IF ITAR:** Comply with export control regulations for [item_type]
- Provide [warranty_terms] and [support_requirements]

**NEVER USE FRAGMENTS like "Standard warranty" - make it complete: "Provide standard commercial warranty covering defects in materials and workmanship for minimum 12 months from acceptance"**

---

## 🟩 Key Takeaways for Bidders

**NUMBERED LIST (10-15 items) - Each item should be informative:**

1. Item supplied: [Complete_description with key specs]
2. Quality standard: [Specific_standard with certification requirements]
3. Inspection/acceptance: [Specific_location and agency] - coordinate [timeframe] before shipment
4. Delivery terms: FOB [Point], ship to [Specific_location]
5. Lead time: [Specific_timeline with trigger event]
6. Contract duration: [Years] [Type] contract with [Options_details]
7. Systems required: [List_all - WAWF, PIEE, WIMS, etc.]
8. Packaging: [Specific_standard with preservation level]
9. Documentation: [Specific_requirements - traceability, test reports, etc.]
10. Certifications: [Complete_list with specific requirements]
11. **IF Special Requirements:** [List_all - FAT, ITAR, security clearance, etc.]
12. **IF All-or-None:** Quote must include all items - partial quotes not accepted
13. Submission deadline: [CAMP_SABLE_DEADLINE] via email to john@campsable.com
14. **IF Contact Provided:** Coordinate inspection with [Name] at [Phone/Email]
15. **Additional Key Point if Applicable**

---

END OF RFQ
```

## CRITICAL GENERATION NOTES

### Do NOT Output:
- Placeholder text like "[Extract from...]" or "[Extract exact...]"
- Incomplete sentences or fragments
- HTML comments or tags
- Bold formatting (**) in body text (EXCEPTION: table headers MUST be bold)
- Government emails (.mil, .gov)
- Generic vague statements

### DO Output:
- Complete professional sentences
- Specific extracted data
- Proper emoji (🏛️ for sections, 🟩 for summaries)
- Only john@campsable.com as contact
- Camp Sable deadline (government deadline - 4 business days)
- **Bold headers in ALL tables** for visibility

### Quality Checks Before Finalizing:
1. All sections present and complete
2. No placeholder text visible
3. CLIN table appropriate to item count (summary if 20+)
4. Delivery address complete (not missing)
5. Professional tone throughout
6. Tables properly formatted **with bold headers**
7. Emoji correct (🏛️ not 🛒)
8. Signature is "[My signature info]"
"""

SERVICE_RFQ_PROMPT = f"""{EXTRACTION_RULES}

## SERVICE RFQ TEMPLATE

Generate following this EXACT structure. Match "Claude Service List.odt" precisely.

[INSTRUCTION: Output only the markdown content below. Do not output these instructions.]

```markdown
# [PROJECT TITLE IN ALL CAPS]

Notice ID: [Solicitation_Number]

Dear [Vendor]:

We are writing to request a formal quote for [specific_service_type]. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

Your response is needed on or before [CAMP_SABLE_DEADLINE] in order for us to submit your bid.

All requirements, specifications, and compliance criteria are detailed below. Please review the complete RFQ carefully. If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

[My signature info]

---

## 🟩 In Summary

**EXACTLY 3 BULLETS - BE SPECIFIC WITH QUANTITIES AND LOCATIONS:**

- They want: [Specific_scope with quantities and technical details - e.g., "Reforest and manage 175 acres of mitigation land with tree planting, invasive species control, and 3-year monitoring"]
- Time frame: [Specific_dates - e.g., "March 1, 2026 through December 31, 2028 (3-year contract)"]
- Delivery locations: [Specific_locations - e.g., "9 sites across Cass County, ND and Clay County, MN near Fargo-Moorhead area"]

---

## 🏛️ Summary of Project

Title: [Complete_Official_Project_Title]
Type: [Contract_Type - Firm Fixed Price, etc.]
Purpose: [Detailed_purpose extracted from PWS Section 1 or Executive Summary - multiple sentences if needed]

Location:
- [State_1]: [Counties/Cities/Areas]
- [State_2]: [Counties/Cities/Areas]

Total Work Area:
- Base Contract: [Specific_scope - e.g., "165.4 acres" or "67 facilities" or "18-month period"]
- Option 1: [Specific_option_scope - e.g., "+10.4 acres" or "+5 facilities" or "+6 months"]

Project Objective:
[Extract verbatim from PWS or synthesize: 2-4 complete sentences explaining what success looks like - include performance standards if mentioned]

---

## 🏛️ What They Want (Scope of Work)

[INSTRUCTION: Extract specific tasks from PWS/SOW. Do not use generic summaries.]

| **Category** | **Main Tasks** |
|----------|------------|
| [Category_1] | [Detailed_tasks_with_specifics - DO NOT just say "See PWS" - LIST the actual tasks] |
| [Category_2] | [Detailed_tasks_with_specifics] |
| [Category_3] | [Detailed_tasks_with_specifics] |

---

## 🏛️ Timeline / Period of Performance

[INSTRUCTION: Extract specific dates and activities. If dates are missing, use "TBD at Task Order".]

| **Year/Phase** | **Dates** | **Requirements** |
|------------|-------|--------------|
| Year 1 | [Start_Date] → [End_Date] | [All_major_activities_and_deliverables - be specific] |
| Year 2 | [Start_Date] → [End_Date] | [All_major_activities_and_deliverables] |
| Year 3 | [Start_Date] → [End_Date] | [All_major_activities_and_deliverables] |

**IF OPTIONS EXIST:**
Option 1 (if exercised): [Complete_option_details with dates and scope]

---

## 🏛️ Deliverables & Reporting Deadlines

- Initial Submittals: [List specific items or "Safety Plan and Project Schedule within 15 days of award"]
- Monthly: [Specific requirements or "Status Report accompanying invoice"]
- Annually: [Specific requirements or "Annual Performance Summary"]
- Final: [Final deliverables or "Final Report and site turnover inspection"]

---

## 🏛️ Delivery / Work Locations

Work occurs across [X] sites:

**LIST ALL SITES WITH SPECIFIC DETAILS:**

[State_1] Sites:
- [Site_ID or Name]: [Complete_address or location description], [Size - acreage/sq ft], [Type - forest/prairie/facility]
- [Site_ID or Name]: [Complete_address or location description], [Size], [Type]

General Delivery/Access:
- [Access_details - roads, gates, coordination requirements]
- [Coordination_requirements - notify before entry, traffic control, etc.]

[INSTRUCTION: If specific address missing, write "To be coordinated with Contracting Officer Representative (COR)"]

---

## 🏛️ Key Compliance Points

- Use: [Specific_systems - e.g., "Resident Management System (RMS) for all submissions" or "Standard industry equipment"]
- Meet: [Safety_standards - e.g., "EM 385-1-1 Safety Requirements" or "Applicable Federal/State regulations"]
- Licensing requirements: [Specific_licenses - e.g., "Licensed herbicide applicators" or "Applicable professional licenses"]
- Environmental compliance: [Specifics - e.g., "Obtain NPDES permits" or "Comply with local environmental mandates"]
- Quality control: [Specifics - e.g., "Industry standard Quality Control Plan"]
- Wage Determination: [WD_Number] for [States] - [Sample_classification]: $[Rate]/hour + $[Benefits] fringe
- Insurance Requirements: [All_requirements with specific amounts or "Per FAR 52.228-5 and state statutory minimums"]

[INSTRUCTION: Never use 'Not specified'. If data is missing, use a professional default from EXTRACTION_RULES.]

---

## 🏛️ Acceptance Criteria

To be accepted, each site must:

- [Specific_criterion_1 - e.g., "Achieve minimum 450 live seedlings ≥30 inches tall per acre"]
- [Specific_criterion_2 - e.g., "Maintain >50% native vegetation cover"]
- [Specific_criterion_3 - e.g., "Reduce invasive species to <15% total cover"]
- Pass final walkthrough - deficiencies corrected at contractor expense

---

## 🏛️ General Overview

- Project Name: [Official_Project_Name]
- Solicitation Number: [Number]
- Agency: [Full_Agency_Name] -- [Sub-agency or District]
- Delivery Period: [Start_Date] to [End_Date]
- Location: [Geographic_summary]
- Type: [Contract_Type]
- Set-Aside: [Set-Aside_Type - e.g., "100% Women-Owned Small Business (WOSB)"]

---

## 🏛️ Key Requirements

### Certification & Capability
- [Specific_certifications - e.g., "Forestry contractor license in MN and ND"]
- [Experience_requirements - e.g., "Minimum 3 years experience"]
- [Personnel_requirements - e.g., "Licensed arborist on staff"]

### Technical Standards
- [Standard_1 - e.g., "EM 385-1-1 USACE Safety Manual"]
- [Standard_2 - e.g., "OSHA 1926 Construction Standards"]

### Wage & Labor Compliance
- Wage Determination: [WD_Number - e.g., "WD 2015-4191 (Revision 23)"]
- Applicable States: [States]
- Sample Classifications and Rates:
  - [Classification_1]: $[Rate]/hour (base) + $[Amount] H&W + [Other_fringes]

### Security & Compliance
- Clearance requirements: [Specifics or "Standard background checks for facility access"]
- Training requirements: [Specifics or "Standard contractor safety and compliance training"]
- Compliance systems: [Specifics or "WAWF/PIEE for invoicing"]

### Insurance Requirements
- General Liability: $[Amount] per occurrence [or "Required per FAR 52.228-5"]
- Auto Liability: $[Amount] combined single limit
- Workers Compensation: Statutory requirements for [specific_states]

**IF NOT SPECIFIED IN DOCUMENTS:**
- General Liability: Required (amounts to be determined per contract requirements)
- Auto Liability: Required (amounts to be determined per contract requirements)
- Workers Compensation: Required per state law for Minnesota and North Dakota
- Employers Liability: Required (amounts to be determined per contract requirements)

---

## 🏛️ Bid Submission Instructions

### Submission Method & Contact
- Format: [Email or Other] [If email: "PDF attachments preferred"]
- Recipient: john@campsable.com
- Subject line: [Format - e.g., "Quote for W912ES26BA007 - Fargo Forest Planting"]
- Deadline: [CAMP_SABLE_DEADLINE]

### Required Quote Content
**CRITICAL: ONLY INCLUDE WHAT THE BIDDER MUST SUBMIT - NOT CAMP SABLE INTERNAL REQUIREMENTS**
**EXTRACT FROM SECTION L OR SUBMISSION INSTRUCTIONS, BUT FILTER OUT:**
- SF 1449 form completion (Camp Sable handles this)
- Government-specific forms that Camp Sable completes
- Items marked "for prime contractor" when Camp Sable is the prime

**BIDDER MUST PROVIDE:**
1. [Requirement_1 - e.g., "Itemized pricing for base and option periods"]
2. [Requirement_2 - e.g., "Company qualifications and relevant experience"]
3. [Requirement_3 - e.g., "List of key personnel with licenses"]
4. [Requirement_4 - e.g., "Equipment list and availability"]
5. [Requirement_5 - e.g., "Technical proposal outlining approach and capabilities"]
6. [Continue_all_bidder_requirements - exclude forms Camp Sable completes]

### Evaluation Criteria
- Award basis: [Extract - e.g., "Lowest Price Technically Acceptable (LPTA)" or "Best Value"]
- Evaluation factors: [List_from_Section_M]
- [Special_considerations - e.g., "All-or-None basis"]

---

## 🏛️ Base Contract Scope

**EXTRACT EVERY BASE CLIN FROM SF 1449:**

| **CLIN** | **Item Description** | **Quantity** | **Unit** | **Notes** |
|------|------------------|----------|------|-------|
| [CLIN] | [Complete_Description] | [Qty] | [Unit] | [Notes] |
| [CLIN] | [Complete_Description] | [Qty] | [Unit] | [Notes] |

Total Base Contract Price for [Description_of_base_scope]

---

## 🏛️ Option 1 Scope

**IF OPTIONS EXIST - EXTRACT EVERY OPTION CLIN:**

| **CLIN** | **Item Description** | **Quantity** | **Unit** | **Notes** |
|------|------------------|----------|------|-------|
| [CLIN] | [Complete_Description] | [Qty] | [Unit] | [Notes] |

Total Option 1 Price for [Description_of_option_scope] (if exercised)

**IF NO OPTIONS:**
Not Included in This Solicitation - This is a [X]-year contract with no option periods.

---

## 🏛️ ATTACHMENTS PROVIDED

**LIST EVERY ATTACHMENT WITH DESCRIPTIVE PURPOSE:**
- [Attachment_1_Name]: [Brief_description_of_contents and purpose]
- [Attachment_2_Name]: [Brief_description_of_contents and purpose]
- [Attachment_3_Name]: [Brief_description_of_contents and purpose]

**EXAMPLE:**
- Attachment 1 - Deliverable Schedule: Lists all required submittals, due dates, formats, and recipients
- Attachment 2 - Approved Herbicide List: EPA-approved chemicals for invasive species control with application notes
- Attachment 3 - Site Mapbook: Detailed maps showing all work locations, boundaries, and access points

---

## 🟩 Summary for Bidders

**NUMBERED LIST (8-12 COMPLETE SENTENCES - NOT FRAGMENTS):**
**CRITICAL: LAST ITEM MUST USE [CAMP_SABLE_DEADLINE] VARIABLE FOR CONSISTENCY**

1. [Complete_summary_of_what_to_perform - e.g., "Prepare all required plans (schedule, safety, QC, herbicide, maintenance) and submit within specified deadlines"]
2. [Standards_and_compliance - e.g., "Conduct all work in compliance with EM 385-1-1 safety standards, OSHA regulations, and environmental permits"]
3. [Key_deliverables - e.g., "Plant approximately 69 acres with native species, maintain for 3 years, and achieve final vegetation performance standards"]
4. [Timeline - e.g., "Complete initial planting by end of Year 1 growing season; continue maintenance and monitoring through Year 3"]
5. [Work_locations - e.g., "Work occurs at 9 sites across Cass County, ND and Clay County, MN with varying access requirements"]
6. [Performance_standards - e.g., "Meet specific survival rates, coverage targets, and invasive species control thresholds by end of contract"]
7. [Wage_compliance - e.g., "Pay prevailing wages per WD 2015-4191 for Minnesota and North Dakota with proper documentation"]
8. [Submission - e.g., "Submit quote to john@campsable.com by [CAMP_SABLE_DEADLINE] with all required documentation and pricing"]

---

## 🟩 Key Takeaways for Bidder

**CRITICAL: MUST USE CHECKBOX FORMAT [ ] - NOT NUMBERED LIST - NOT REGULAR BULLETS**
**CRITICAL: LAST CHECKBOX MUST USE [CAMP_SABLE_DEADLINE] VARIABLE - NEVER HARDCODE A DIFFERENT DATE**

- [ ] [Takeaway_1 - actionable item - e.g., "Submit all required plans (schedule, safety, QC, herbicide, maintenance) within 30 days of award"]
- [ ] [Takeaway_2 - e.g., "Obtain and maintain licensed herbicide applicators in ND and MN; use only approved EPA chemicals"]
- [ ] [Takeaway_3 - e.g., "Complete site preparation and planting of 68.8 acres during Year 1 growing season"]
- [ ] [Takeaway_4 - e.g., "Perform invasive species control on 96.5 acres using approved herbicides with proper documentation"]
- [ ] [Takeaway_5 - e.g., "Submit monthly maintenance reports (April-October) and annual monitoring reports (by January 30)"]
- [ ] [Takeaway_6 - e.g., "Meet final performance standards: >450 seedlings/acre ≥30\" tall, >50% native cover, <15% invasive cover"]
- [ ] [Takeaway_7 - e.g., "Pay prevailing wages per WD 2015-4191; maintain certified payroll and fringe benefit records"]
- [ ] [Takeaway_8 - e.g., "Provide required insurance: GL, Auto, WC, and Employers Liability per specified amounts"]
- [ ] [Takeaway_9 - e.g., "Use Resident Management System (RMS) for all electronic submissions"]
- [ ] [Takeaway_10 - e.g., "Coordinate access with Contracting Officer; provide 10-day notice for ground disturbance"]
- [ ] [Takeaway_11 - e.g., "Complete corrective actions for any deficiencies found during final walkthrough at contractor expense"]
- [ ] [Takeaway_12 - e.g., "Submit quote to john@campsable.com by [CAMP_SABLE_DEADLINE] with itemized pricing for base and option"]

**NEVER USE:**
- Regular bullets: `- Item` ❌
- Numbered list: `1. Item` ❌
- **ONLY USE:** Checkboxes: `- [ ] Item` ✅

---

END OF RFQ
```

## CRITICAL GENERATION NOTES FOR SERVICE RFQs

### Service-Specific Extraction Priorities:
1. **PWS/SOW**: This is your primary source - read completely
2. **Wage Determination**: Extract complete classification and rate tables
3. **Site Locations**: Get complete addresses or descriptions
4. **Deliverables**: Extract specific due dates (not just "monthly" - extract which day of month)
5. **Performance Standards**: Extract measurable criteria with numbers

### Common SERVICE Mistakes to Avoid:
- ❌ "Perform work as per PWS" (extract actual tasks)
- ❌ "Wage determination applies" (extract WD number and sample rates)
- ❌ "Various sites" (list all sites with locations)
- ❌ "Submit reports" (specify which reports and when)
- ❌ Using numbered list for Key Takeaways (must use [ ] checkboxes)

### Quality Checks for SERVICE:
1. "In Summary" section at TOP with exactly 3 bullets
2. Wage Determination number extracted (e.g., WD 2015-4191)
3. All sites listed with locations
4. Performance standards are measurable (numbers, percentages)
5. Key Takeaways use `- [ ]` format
6. No "See PWS" anywhere - actual content extracted
"""