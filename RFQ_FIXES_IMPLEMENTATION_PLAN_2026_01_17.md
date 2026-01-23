# Fix RFQ Quality Issues - Implementation Plan

## Problem Statement

Client reviewed the generated RFQ file `27a6a68dd9eb4bd69eee2c5787d6ba16_RFQ_PRODUCT.docx` (Custom Surgical Packs, 98/100 quality score) and identified critical issues:

1. **Inconsistent Dates** - Dates appear in multiple places with inconsistent formatting or values
2. **Missing Table Headers** - CLIN table lacks clear column headers, making it meaningless
3. **Incomplete Requirements Disclosure** - RFQ says "There are other documents that I can send you, if this is a project that you would be interested in bidding" - This is WRONG! Vendors need ALL requirements upfront, not a teaser
4. **Poor Certification Formatting** - Certifications section mixes Camp Sable requirements with actual government requirements without clear distinction

> [!WARNING]
> The current approach of asking vendors "if they're interested" defeats the purpose of an RFQ. Vendors cannot make informed decisions without complete information upfront.

## Root Cause Analysis

### Issue 1: Inconsistent Dates
**Location:** `rfq_prompts.py` lines 108-118, 285-286
- Multiple date references: Solicitation Date, Quotes Due, Posted Date
- Camp Sable deadline calculation may be inconsistent
- Date formatting varies across sections

### Issue 2: Missing Table Headers
**Location:** `rfq_prompts.py` lines 324-350
- The CLIN table template has headers defined in the prompt
- However, the generated output shows headers are not being rendered properly
- Likely issue: Headers are on separate lines without proper markdown table formatting

### Issue 3: Incomplete Requirements
**Location:** `rfq_prompts.py` lines 264-268
- Line 268: "There are other documents that I can send you, if this is a project that you would be interested in bidding."
- This is a placeholder/template text that should NOT be in the final RFQ
- Vendors need complete information to make informed bids

### Issue 4: Certification Formatting
**Location:** `rfq_prompts.py` lines 446-462
- Certifications are listed with conditional logic markers (`**IF Defense:**`, `**IF ITAR:**`)
- Camp Sable-specific requirements (SAM.gov, FAR 52.212-3) are mixed with government requirements
- No clear visual separation or explanation

---

## Proposed Changes

### 1. Fix Date Consistency

#### [MODIFY] [rfq_prompts.py](file:///Users/apple/Downloads/rebusinessautomationproject/ai_agents/AttachmentReaderAgent/rfq_prompts.py)

**Changes:**
- Standardize all date references to use consistent format: `Month DD, YYYY` (e.g., "January 13, 2026")
- Ensure Camp Sable deadline is clearly calculated and displayed consistently
- Add validation in extraction rules to ensure date consistency
- Update lines 108-118 to specify single date format
- Update lines 283-286 to use consistent date variables

**Specific Updates:**
```python
# Lines 108-118: Standardize date format
**Dates and Deadlines**
**Use ONLY this format:** Month DD, YYYY (e.g., "January 13, 2026")
- Solicitation Posted Date: [Extract and convert to Month DD, YYYY]
- Government Deadline: [Extract and convert to Month DD, YYYY]
- Camp Sable Deadline: [Government deadline - 4 BUSINESS days, formatted as Month DD, YYYY]

# Lines 283-286: Use consistent date references
Solicitation Date: [Posted_Date in Month DD, YYYY format]
Quotes Due: [CAMP_SABLE_DEADLINE in Month DD, YYYY format]
```

### 2. Fix Table Headers

#### [MODIFY] [rfq_prompts.py](file:///Users/apple/Downloads/rebusinessautomationproject/ai_agents/AttachmentReaderAgent/rfq_prompts.py)

**Changes:**
- Ensure CLIN table headers are on a single line with proper markdown pipe formatting
- Add explicit instruction to ALWAYS include the header row
- Update lines 324-350 to emphasize header row requirement

**Specific Updates:**
```python
# Lines 324-350: Emphasize table headers
## CLIN Table

**CRITICAL: ALWAYS include the header row as the FIRST row of the table**

**IF TOTAL ITEMS = 1-19:** Use detailed format (list every item)

| CLIN | Description | Quantity | Contract Type | Inspection | Packaging | Notes |
|------|-------------|----------|---------------|------------|-----------|-------|
| [CLIN] | [Full_Description] | [Qty] [Unit] | [Type] | [Point] | [Standard] | [Notes_or_"None"] |

**IF TOTAL ITEMS = 20+:** Use summary format (group by category)

| CLIN Range | Category | Item Count | Contract Type | Inspection | Packaging | Notes |
|------------|----------|------------|---------------|------------|-----------|-------|
| 1-10 | [Category_Name] | 10 items | FFP | Destination | Commercial | [Brief_description_or_"Standard"] |
```

### 3. Remove Incomplete Requirements Language

#### [MODIFY] [rfq_prompts.py](file:///Users/apple/Downloads/rebusinessautomationproject/ai_agents/AttachmentReaderAgent/rfq_prompts.py)

**Changes:**
- Remove the line "There are other documents that I can send you, if this is a project that you would be interested in bidding."
- Replace with language that indicates ALL requirements are included in the RFQ
- Update lines 264-272

**Specific Updates:**
```python
# Lines 264-272: Replace with complete requirements language
Your response is needed on or before [CAMP_SABLE_DEADLINE] in order for us to submit your bid.

All requirements, specifications, and compliance criteria are detailed below. Please review the complete RFQ carefully and contact me if you need any clarification. If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.
```

### 4. Improve Certification Formatting

#### [MODIFY] [rfq_prompts.py](file:///Users/apple/Downloads/rebusinessautomationproject/ai_agents/AttachmentReaderAgent/rfq_prompts.py)

**Changes:**
- Separate Camp Sable requirements from government requirements
- Remove conditional logic markers from output (keep in extraction logic only)
- Use clear section headers and formatting
- Update lines 446-462

**Specific Updates:**
```python
# Lines 446-462: Improve certification section structure
## 🏛️ REQUIRED CERTIFICATIONS & COMPLIANCE

**EXTRACTION LOGIC:**
- Check evaluation criteria section
- Look for special provisions
- Note FAR/DFARS clauses
- Identify mandatory certifications

**OUTPUT FORMAT:**

### Government Requirements
[List only certifications explicitly required by the government solicitation]
- [Certification 1 with specific details]
- [Certification 2 with specific details]
- [Certification 3 with specific details]

### Camp Sable Requirements (for all bidders)
- ISO 9001:2015 or equivalent quality management system
- SAM.gov registration (active and current)
- FAR 52.212-3 Representations and Certifications (complete)

**IMPORTANT:** List each requirement on its own line without conditional markers. Only include government requirements that are explicitly stated in the solicitation documents.
```

---

## Verification Plan

### Automated Tests

#### Test 1: Regenerate the Same RFQ
```bash
# Navigate to project directory
cd /Users/apple/Downloads/rebusinessautomationproject

# Regenerate the Custom Surgical Packs RFQ
python main_workflow.py \
  --mode extract-and-generate-rfq \
  --url "https://sam.gov/opp/36C24626Q0146" \
  --strict-fidelity \
  --max-healing-iterations 2
```

**Expected Results:**
- ✅ All dates in "Month DD, YYYY" format
- ✅ CLIN table has visible headers on first row
- ✅ No mention of "other documents I can send you"
- ✅ Certifications clearly separated into Government vs Camp Sable sections

#### Test 2: Validate Output Quality
```bash
# Check the generated file
python -c "from docx import Document; doc = Document('./rfq_downloads/2026-01-17/[generated_file].docx'); print('\\n'.join([p.text for p in doc.paragraphs[:150]]))"
```

**Manual Checks:**
1. Search for "There are other documents" - should return 0 results
2. Search for "**IF" - should return 0 results (no conditional markers)
3. Count date formats - all should match "Month DD, YYYY"
4. Verify CLIN table has header row with column names

### Manual Verification

**User Action Required:**
After regeneration, please review the new RFQ file and confirm:

1. **Date Consistency**: All dates appear in the same format throughout
2. **Table Headers**: CLIN table clearly shows what each column represents
3. **Complete Requirements**: RFQ states all requirements are included, not asking if vendor is interested
4. **Certification Clarity**: Clear distinction between government requirements and Camp Sable requirements

---

## Implementation Notes

- All changes are in `rfq_prompts.py` - no code logic changes needed
- Changes affect the PRODUCT_RFQ_PROMPT template
- Self-healing system should still work as before
- Quality score should remain 95+ after fixes

