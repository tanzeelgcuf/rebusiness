# Comprehensive AI Agent Implementation Prompt: SAM.gov Extraction System Upgrade

**Role:** Senior AI Systems Architect & Python Developer
**Context:** You are upgrading an existing multi-agent system (`SamGovAgent`, `AttachmentReaderAgent`, `ProposalWriter`) to become an "Elite Procurement Intelligence Agent". The current codebase uses Playwright, Gemini/OpenAI, and basic file handlers.
**Goal:** Refactor and enhance the system to achieve 100% data extraction accuracy, zero placeholders, and perfect ODT template alignment.

---

## 1. High-Level Objectives
1.  **Deep Crawling**: Ensure deep link validation reaches 2-3 levels deep for comprehensive attachment discovery.
2.  **Advanced Document Processing**: Replace `PyPDF2` with `pdf-extract-kit` (or a robust Gemini Vision fallback if kit fails) for table extraction.
3.  **Zero-Placeholder Policy**: Enforce a strict "No N/A" rule. If data is missing in the main text, the agent must trigger web research (SerpAPI) or deep document scanning.
4.  **Template-Compliant Output**: The JSON output from `AttachmentReaderAgent` must EXACTLY match the fields required by `Claude Vendor List.odt` (Products) and `Claude Services List.odt` (Services).

---

## 2. Specific Code Modifications

### A. `ai_agents/SamGovAgent/sam_gov_agent.py`
**Upgrade Task:**
-   **Method `process_detail_page`**:
    -   Enhance `_extract_external_links` to be recursive (max depth 2). Current implementation finds links but doesn't recursively scrape *their* content effectively into the analysis context.
    -   Ensure `_deep_download_attachments` handles "Terms of Service" modals (click "Accept").

### B. `ai_agents/AttachmentReaderAgent/attachment_reader_agent.py`
**Upgrade Task:**
-   **Import**: Add `from pdf_extract_kit import Extractor` (handle import error gracefully).
-   **Method `_read_pdf_file`**:
    -   **Primary**: Try `pdf-extract-kit` to get structured tables (Markdown format).
    -   **Secondary**: Use Gemini Flash (Multimodal) if file size permits.
    -   **Fallback**: `PyPDF2` (keep existing).
-   **Method `_analyze_content_with_llm`**:
    -   **System Prompt Update**: REPLACE the existing `system_instruction` with the **"Master Federal Procurement Analyst"** prompt provided below.
    -   **Schema Enforcement**: Ensure the output JSON structure has specific keys for `clins`, `ship_to_address`, `packaging`, `compliance`.
    -   **Validation**: Add a check `_validate_completeness(analysis)`. If `ship_to_address` is "See solicitation" or missing, trigger `_research_missing_data`.

### C. `ai_agents/ProposalWriterAgent/proposal_writer.py`
**Upgrade Task:**
-   **Logic Update**: The `create_bid_request` function currently generates a generic email. Refactor it to:
    1.  Accept the *enhanced* analysis JSON.
    2.  Check `solicitation_type` (Product vs Service).
    3.  Generate the email body to align with the ODT fields. Use the **exact** formatting required by the `Claude Vendor List.odt` template (e.g., CLIN tables, specific headers).

---

## 3. The "Master Federal Procurement Analyst" System Prompt
*(Replace the variable `system_instruction` in `attachment_reader_agent.py` with this)*

```text
You are a MASTER Federal Procurement Analyst. Your mission is to extract ALL information with ZERO placeholders.

**CRITICAL RULES:**
1. **Notice ID**: Extract character-perfect (e.g., W912ES26BA007).
2. **Quantities**: Must be numeric with units (118 EA, not "See Schedule").
3. **Addresses**: Extract complete Ship-To block (Street, City, State, Zip).
4. **Calculated Dates**: Convert "30 Days ARO" to specific estimated dates based on today's date ({current_date}).
5. **Tables**: Extract CLIN tables completely (Item, Qty, Unit, Price Format).

**OUTPUT SCHEMA (JSON):**
{
  "notice_id": "...",
  "solicitation_type": "PRODUCT" | "SERVICE",
  "dates": { "posted": "YYYY-MM-DD", "due": "YYYY-MM-DD", "internal_due": "YYYY-MM-DD" },
  "soliciting_entity": { "name": "...", "address": "..." },
  "product_specifications": { "nsn": "...", "part_number": "...", "description": "..." },
  "service_scope": { "pws_summary": "...", "locations": ["..."] },
  "clins": [ { "clin": "001", "description": "...", "qty": 10, "unit": "EA" } ],
  "delivery_requirements": { "ship_to_address": "...", "lead_time": "..." },
  "compliance": { "set_aside": "...", "wage_determination": "..." },
  "missing_data_report": ["List any truly missing critical fields"]
}
```

---

## 4. Execution Plan
1.  **Install Dependencies**: `pip install pdf-extract-kit` (ensure system deps are met).
2.  **Refactor `SamGovAgent`**: Add robust deep crawler for comprehensive attachment discovery.
3.  **Refactor `AttachmentReaderAgent`**: Swap LLM prompt and add PDF-Extract-Kit.
4.  **Verify**: Run `run_agents_workflow.py` or `main_workflow.py` on a known complex solicitation URL.

**Instruction to Agent:** Use this prompt to guide your code editing. Focus on file `ai_agents/SamGovAgent/sam_gov_agent.py` and `ai_agents/AttachmentReaderAgent/attachment_reader_agent.py` first.
