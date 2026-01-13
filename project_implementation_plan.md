# Enhancing SamGovAgent Crawling

## Goal Description
Enhance `SamGovAgent` to perform deeper crawling of SAM.gov solicitations. This includes extracting external links (like PDFs hosted elsewhere), explicitly searching for Wage Definitions (WD), and extracting structured line item data from SF 1449 forms if present. This ensures the downstream `AttachmentReaderAgent` has all necessary documents to generate faithful RFQs.

## User Review Required
> [!NOTE]
> This requires adding `BeautifulSoup` parsing logic and `requests` for downloading external files. Ensure these dependencies are available.

## Proposed Changes

### AI Agents
#### [MODIFY] [sam_gov_agent.py](file:///Users/apple/Downloads/rebusinessautomationproject/ai_agents/SamGovAgent/sam_gov_### Adaptation to Playwright Architecture
The user provided code snippet was based on Selenium and BeautifulSoup. We have successfully adapted this to the existing Playwright architecture by:
1.  **Done**: Updating `process_detail_page` in `sam_gov_agent.py` to use `self.page.goto` and `self.page.content()` for navigation and HTML retrieval.
2.  **Done**: Converting `_extract_external_links` to use BeautifulSoup on the HTML content obtained via Playwright.
3.  **Done**: Reusing the `_download_external_document` logic with `requests` as a helper method.
4.  **Done**: Integrating `_deep_download_attachments` (Playwright-based) into the new `process_detail_page`.
### Extraction Fidelity Improvements (User Directed)
To resolve "inaccurate and empty" RFQs and improve fidelity, we will implement the specific code provided by the user:

1.  **Enhance Description Extraction (`SamGovAgent`)**:
    -   Add `_extract_description_comprehensive` to try 5 different strategies for description text.
    -   Update `process_detail_page` to use this new extraction method.

2.  **Simplify Structured Extraction (`AttachmentReaderAgent`)**:
    -   Replace `_extract_structured_data` with a reliable, simplified version focusing on key fields (Notice ID, NAICS, Dates, etc.) and limiting regex search to the first 50K chars.
    -   Replace `_enhance_content_with_context` to inject a clear "CRITICAL INFORMATION" block.

3.  **Optimize LLM Generation (`AttachmentReaderAgent`)**:
    -   Replace `_generate_rfq_with_llm` to:
        -   Use `gemini-2.0-flash-exp` with `max_output_tokens=8192`.
        -   Implement intelligent content truncation (~500k chars).
        -   Inject strict deadline instructions.
    -   Replace `_validate_rfq_completeness` with checks for length, sections, and formatting.

4.  **Fix DOCX Reading (`AttachmentReaderAgent`)**:
    -   Update `_read_docx_file` to iterate through tables and extract cell text, as the current implementation only reads paragraphs, missing critical Parts List data.

5.  **Maximize Data Fidelity (`rfq_prompts.py`)**:
    -   Update `PRODUCT_RFQ_PROMPT` and `SERVICE_RFQ_PROMPT` to:
        -   **Force Inference**: Explicitly default to "Firm Fixed Price", "FOB Destination", "ISO 9001" if not found.
        -   **Ban "See Attachment"**: Instruct the model to extract and list line items/CLINs directly in the markdown tables.
        -   **Ban "Not Specified"**: Replace the "Max 2 times" rule with a "Make a reasonable inference based on FAR standards" rule.
    -   Ensure `SERVICE_RFQ_PROMPT` aligns with `Claude Services List.odt` structure.

### Imports
- **Added**: `requests` and `BeautifulSoup` (bs4) to `sam_gov_agent.py`.
- **Note**: `requests` is used for downloading external documents where Playwright's download handler might be less direct for simple hrefs found by BS4. Start with `verify=False` for now as requested, but add a TODO for security.

### New/Enhanced Methods in `SamGovAgent`
1.  `_extract_external_links(self, soup)`: **Implemented**
2.  `_download_external_document(self, url, save_dir)`: **Implemented**
3.  `_extract_wage_determination(self, soup, save_dir)`: **Implemented**
4.  `_extract_sf1449_data(self, soup)`: **Implemented**
5.  `process_detail_page(self, url)`: **Enhanced & De-duplicated**

### Changes in `AttachmentReaderAgent`
1.  **Indentation Fix**: Moved `_extract_structured_data`, `_enhance_content_with_context`, `_validate_rfq_completeness`, and `_generate_rfq_with_llm` inside the class definition.
- **Replace/Update Method** `process_detail_page(self, url)`:
    - Use `self.page.goto(url)` instead of `self.driver.get`.
    - Create `soup` from `self.page.content()`.
    - Use existing `_deep_download_attachments(self.page, attachment_dir)` for standard attachments instead of the undefined `_download_attachments(soup...)`.
    - Integrate the extraction logic for title, description, SF1449, and external links as requested.

## Verification Plan

### Automated Tests
- None existing for the scraper.

### Manual Verification
1.  **Run Extraction**: Execute the agent against a known SAM.gov solicitation URL that has external links or SF 1449 data.
    - Command: `python3 main_workflow.py --url <URL> --test-extraction` (or equivalent if test mode exists)
    - Alternatively, invoke `SamGovAgent.process_detail_page(url)` directly in a python script.
2.  **Inspect Output**:
    - Check the `attachments` directory for the contract ID.
    - Verify "external_document.pdf" or similar files exist.
    - Verify `description.txt` is populated.
    - Verify console logs show "Found X external links" and "Extracted X CLINs".
