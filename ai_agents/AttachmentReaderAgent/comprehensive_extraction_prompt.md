# COMPREHENSIVE AI AGENT PROMPT: SAM.gov Solicitation Extraction & RFQ Generation

## PRIMARY MISSION
Extract ALL information from SAM.gov solicitations (including main page, all attachments, linked documents, and embedded PDFs/Excel files) and generate a complete, formatted Request for Quote (RFQ) email using the appropriate template based on solicitation type.

---

## PHASE 1: SOLICITATION TYPE DETECTION & TEMPLATE SELECTION

### Step 1: Analyze Solicitation Type
First, determine if the solicitation is for:
- **PRODUCTS/SUPPLIES** → Use "Claude Vendor List" Template
- **SERVICES/MAINTENANCE** → Use "Claude Services List" Template

**Detection Keywords:**
- **Products:** NSN, part number, CAGE code, "supply", "equipment", "material", "assembly", "component", "hardware", quantity in "EA" (each)
- **Services:** PWS (Performance Work Statement), SOW (Statement of Work), "maintenance", "planting", "monitoring", "establish", "manage", labor hours, services per acre/job

**Decision Rule:** If solicitation contains PWS, SOW, or service-oriented deliverables → Services Template. If it contains NSN, part numbers, or material quantities → Products Template.

---

## PHASE 2: COMPLETE DATA EXTRACTION PROCESS

### Step 2A: Extract from Main Solicitation Page
Access the SAM.gov URL and extract:

**Critical Header Information:**
- Notice ID / Solicitation Number
- Solicitation Title
- Agency Name and Full Address
- Contract Type (FFP, Cost-Plus, etc.)
- Set-Aside Type (Small Business, WOSB, etc.)
- NAICS Code and Size Standard
- Posted Date / Response Deadline
- Place of Performance
- Point of Contact (Name, Email, Phone)

**Body Content:**
- Full description of requirements
- Background information
- Technical specifications
- Any special instructions
- Evaluation criteria
- Submission requirements

### Step 2B: Extract from ALL Attachments
SAM.gov solicitations include multiple attachments. You MUST download and extract from EVERY attachment:

**Common Attachment Types:**
1. **SF 1449 (Solicitation Form)** - Extract:
   - Line item details and CLINs
   - Quantities and units
   - Delivery schedules
   - Ship-to addresses
   - Contract clauses

2. **Solicitation Body PDF** - Extract:
   - Complete statement of work
   - Technical requirements
   - Performance standards
   - Compliance requirements
   - Deliverable schedules

3. **Amendment Documents** - Extract:
   - Changes to original solicitation
   - Updated deadlines
   - Revised quantities or specifications
   - Q&A responses

4. **Pricing Templates (Excel)** - Extract:
   - CLIN structure
   - Required pricing format
   - Base and option years
   - Quantity breakdowns

5. **Technical Data Packages (TDP)** - Extract:
   - Drawings and specifications
   - Part numbers and nomenclature
   - Material requirements
   - Quality standards

6. **Performance Work Statements (PWS)** - Extract:
   - Scope of work details
   - Deliverables and milestones
   - Performance metrics
   - Inspection criteria

7. **Questions & Clarifications (Q&C)** - Extract:
   - All questions and official answers
   - Additional guidance
   - Clarified requirements

8. **Wage Determinations** - Extract:
   - Applicable labor categories
   - Wage rates by location
   - Fringe benefits

9. **Maps and Site Plans** - Extract:
   - Work locations
   - Site boundaries
   - Access points
   - Coordinates

10. **Approved Materials Lists** - Extract:
    - Acceptable brands/models
    - Specifications for materials
    - Required certifications

### Step 2C: Extract from Linked Documents Within Attachments
Many PDFs contain hyperlinks to additional resources. You MUST:
1. Identify all URLs mentioned in any document
2. Access each linked resource
3. Extract relevant information
4. Cross-reference with main requirements

**Common Linked Resources:**
- Military specifications (MIL-STD, MIL-SPEC)
- Federal regulations (FAR, DFARS)
- Agency-specific guidance documents
- Safety manuals (EM 385-1-1)
- Technical standards (ISO, ASTM)
- Environmental compliance documents

### Step 2D: Parse Embedded Tables and Data
Extract structured data from:
- CLIN tables (item numbers, descriptions, quantities, units)
- Delivery schedules (dates, frequencies, locations)
- Pricing structures (unit prices, totals, options)
- Performance standards (metrics, thresholds, testing requirements)
- Contact lists (names, roles, phone, email)

---

## PHASE 3: INFORMATION CATEGORIZATION & ORGANIZATION

### Step 3A: For PRODUCTS/SUPPLIES (Vendor List Template)
Organize extracted information into these sections:

#### Section 1: EMAIL HEADER
- Subject line with Notice ID and item name
- Professional greeting
- Camp Sable introduction paragraph
- Internal deadline (4 business days before official due date)

#### Section 2: SOLICITATION DETAILS
- Notice ID (exact match from SAM.gov)
- Solicitation Title with NSN
- Issuing Agency and complete address
- Contract Type
- Set-Aside Type
- NAICS Code and Size Standard
- DPAS Rating (if applicable)
- Posted Date
- Official Quote Due Date
- Adjusted internal deadline

#### Section 3: ITEM SPECIFICATIONS
- Item name and drawing number
- Manufacturer CAGE Code
- Manufacturer Part Number
- NSN (National Stock Number)
- Complete technical description
- Reference to TDP availability

#### Section 4: QUANTITIES REQUIRED
Create table with columns:
- CLIN (Contract Line Item Number)
- Description
- Quantity (with unit: EA, LB, etc.)
- Contract Year/Period
- Packaging Requirements
- Notes (minimum guarantees, ordering periods)

Include totals:
- Guaranteed Minimum Quantity
- Maximum Contract Quantity

#### Section 5: DELIVERY REQUIREMENTS
**Delivery Terms:**
- FOB Point (Origin/Destination)
- Complete Ship-To Address (every line)
- Special delivery instructions

**Delivery Schedule:**
- Initial delivery timeframe (days ARO - After Receipt of Order)
- Ongoing delivery frequency
- Early delivery policy
- Contract duration (years)

**Delivery Schedule by CLIN:** (table format)
- Each CLIN with quantities
- Start dates or "As Ordered"
- Delivery frequencies

#### Section 6: PACKAGING REQUIREMENTS
- MIL-STD references (e.g., MIL-STD-2073-1)
- Preservation level
- Quantity per unit pack
- Labeling requirements (e.g., MIL-STD-129)
- SPI references with dates and revisions

#### Section 7: INSPECTION & QUALITY REQUIREMENTS
**Inspection:**
- Inspection point (Origin/Destination)
- Acceptance point
- Responsible agency (DCMA, etc.)
- Notification requirements
- Consequences of non-compliance

**Initial Production Inspection (if required):**
- Sample size requirements
- Verification process
- Approval requirements before full production

**Quality Standards:**
- ISO certifications required
- Testing requirements
- Documentation retention periods

#### Section 8: DATA ACCESS & COMPLIANCE
- TDP availability and access method
- Required certifications (DD2345, JCP, etc.)
- ITAR/Export control requirements
- Security clearance needs

#### Section 9: SUBMISSION INSTRUCTIONS
**What to Include in Quote:**
1. Unit prices per CLIN
2. Total prices per CLIN
3. Overall totals
4. Lead time confirmations
5. Company certifications
6. Technical capability statements
7. Coordination capability confirmations

**Quote Submission:**
- Agency submission (email, subject format, file type, deadline)
- Camp Sable internal submission (adjusted deadline, contact)

#### Section 10: EVALUATION CRITERIA
- Evaluation basis (LPTA, Best Value, etc.)
- Special clauses (All or None, etc.)

#### Section 11: ADDITIONAL CONTACTS
- QA POC information
- Technical questions contact
- Contract specialist

#### Section 12: SUMMARY OF REQUIREMENTS
Numbered list (1-10+) of all key capabilities vendor must demonstrate

#### Section 13: CLOSING
- Questions invitation with contact email
- Professional closing
- Signature block

### Step 3B: For SERVICES/MAINTENANCE (Services List Template)
Organize extracted information into these sections:

#### Section 1: EMAIL HEADER
- Subject line with Notice ID and project name
- Professional greeting
- Camp Sable introduction
- Note about additional documents available
- Internal deadline (4 business days before official)

#### Section 2: SUMMARY OF PROJECT
- Project Title
- Contract Type and Duration
- Purpose/Objective
- Location (states, counties)
- Total Work Area (acres, square footage, etc.)
- Project Goals/Outcomes

#### Section 3: WHAT THEY WANT (Scope of Work)
Table format with major categories:
- Task descriptions
- Detailed requirements for each task
- Expected outcomes

#### Section 4: TIMELINE / PERIOD OF PERFORMANCE
Table with:
- Year/Phase
- Date Range
- Key Activities for each period

Include any option periods

#### Section 5: DELIVERABLES & REPORTING DEADLINES
- Initial submittals (plans, schedules, safety docs)
- Monthly requirements
- Annual reports
- Final deliverables
- All submission deadlines with specific dates

#### Section 6: DELIVERY / WORK LOCATIONS
- Complete list of all work sites
- Site names/numbers
- Addresses or coordinates
- County and State
- Access information
- Special site conditions

#### Section 7: KEY COMPLIANCE POINTS
- Software systems required (RMS, WAWF, etc.)
- Safety requirements (EM 385-1-1, OSHA)
- Licensing requirements
- Environmental compliance
- Permit requirements
- Quality control plans
- Special certifications

#### Section 8: ACCEPTANCE CRITERIA
- Performance standards to meet
- Inspection processes
- Final acceptance requirements
- Consequences of non-compliance

#### Section 9: APPROVED MATERIALS/METHODS LIST
If applicable (e.g., herbicides, equipment):
- Table of approved items
- Specifications
- Usage restrictions
- Documentation requirements

#### Section 10: REQUIRED DOCUMENTATION FORMS
Description of any required forms:
- Post-application documentation
- Daily logs
- Inspection checklists
- Submission formats and deadlines

#### Section 11: SITE MAPS AND LAYOUTS
- Reference to mapbook/attachments
- List of all sites with acreage
- Site classifications
- Base vs. optional sites

#### Section 12: KEY DATES & ACTIONS FOR VENDORS
Table format:
- Action Required
- Deadline
- Reference Document

#### Section 13: SUMMARY FOR BIDDERS
Numbered list of major responsibilities:
1. All plans and submittals required
2. Scope of physical work
3. Maintenance/monitoring duration
4. Special compliance requirements
5. Work locations
6. Performance standards

#### Section 14: SUBMISSION INSTRUCTIONS
**What to Include in Proposal:**
- Technical approach
- Past performance examples
- Personnel qualifications
- Equipment lists
- Insurance certificates
- Licenses and certifications
- Price breakdown

**Submission Details:**
- How to submit (email, hand-delivery, portal)
- Agency contact and address
- Subject line format
- Required format (PDF, etc.)
- Official deadline
- Camp Sable internal deadline

#### Section 15: GENERAL OVERVIEW (Contract Details)
- Project name
- Solicitation number
- Agency and district
- Location summary
- Purpose statement
- Duration with dates
- Contract type
- Set-aside information

#### Section 16: KEY REQUIREMENTS (Compliance Summary)
1. Security/vetting requirements
2. Wage and labor compliance
3. Insurance requirements (with dollar amounts)
4. Veteran hiring preferences
5. Contract clauses to note
6. Limitations on subcontracting
7. Prohibited technologies

#### Section 17: BID SUBMISSION INSTRUCTIONS
1. Due date and time (with timezone)
2. Delivery options (hand-carry, mail - note NO email/fax)
3. Required documents list:
   - SF 1449
   - Bid bonds
   - Pricing sheets
   - Certifications
   - Signed amendments

#### Section 18: POST-AWARD RESPONSIBILITIES
- Self-performance breakdown
- Documentation maintenance
- Invoice submission process
- SAM registration maintenance

#### Section 19: IMPORTANT CONTACTS & REFERENCE INFO
- Contracting Officer name and agency
- Inquiry system (ProjNet, etc.) with access codes
- Inquiry deadlines
- Reference websites

#### Section 20: OVERALL PROJECT SUMMARY RECAP
- Quick overview
- Contract type
- Performance period
- Work includes
- Pricing format notes

#### Section 21: BASE CONTRACT SCOPE
Detailed CLIN breakdown by year:
- Year 1 items (numbered list with descriptions)
- Year 2 items
- Year 3 items (and additional years if applicable)
- Total Base Contract Price deliverable note

#### Section 22: OPTION SCOPE(S)
If applicable, same format as base:
- Option 1, 2, etc. broken down by year
- Total Option Price deliverable note

#### Section 23: TOTALS REQUIRED ON BID FORM
- Total Base Amount
- Total Option Amount(s)
- Combined Total

#### Section 24: KEY TAKEAWAYS FOR BIDDER
Bullet points highlighting:
- Critical pricing requirements
- Units of measure
- Completeness requirements
- Option notes

#### Section 25: CLOSING
- Questions invitation
- Contact information
- Professional sign-off

---

## PHASE 4: FORMATTING REQUIREMENTS

### Markdown Formatting Standards
```markdown
# Use headers for major sections (##, ###)
- Use tables for all structured data
- Use bullet points for lists
- Use **bold** for critical items (Notice ID, deadlines, prices)
- Use horizontal rules (---) between major sections
- Keep consistent spacing and organization
```

### Table Formatting
All tables must be in markdown format:
```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
```

### Critical Emphasis
Use checkmarks for compliance: ✅
Use bold for: **Notice IDs, Deadlines, Contact Emails, Dollar Amounts**

---

## PHASE 5: QUALITY CONTROL CHECKLIST

Before finalizing, verify:

### For ALL Solicitations:
- [ ] Notice ID extracted exactly as shown in SAM.gov
- [ ] ALL attachments downloaded and processed
- [ ] ALL linked documents accessed and information extracted
- [ ] Tables properly formatted with all columns
- [ ] All dates included (no vague references)
- [ ] All addresses complete (no partial addresses)
- [ ] All quantities specified (no "per solicitation" references)
- [ ] Contact information complete (name, email, phone)
- [ ] Internal deadline adjusted to 4 business days before official
- [ ] Camp Sable intro paragraph included
- [ ] Professional opening and closing included
- [ ] bobbysmitty078@gmail.com as contact email

---

## CRITICAL REMINDERS

1. **NEVER skip attachments** - They contain the most detailed information
2. **ALWAYS extract exact quantities** - No vague references
3. **ALWAYS include complete addresses** - Every line matters
4. **ALWAYS specify exact dates** - Not relative references
5. **ALWAYS adjust internal deadline** - 4 business days before official
6. **ALWAYS match Notice ID exactly** - Character-for-character from SAM.gov
7. **ALWAYS determine correct template** - Products vs Services
8. **ALWAYS format tables** - For quantities, schedules, sites, CLINs
9. **ALWAYS include all compliance requirements** - Certifications, standards, regulations
10. **ALWAYS end professionally** - Contact info and closing
