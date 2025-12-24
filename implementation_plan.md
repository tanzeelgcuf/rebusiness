# Upgrade Plan: Universal Deep Digging & Advanced Extraction

## Goal
To upgrade the entire extraction pipeline to robustly capture "meaningful, precise, accurate, complete and exact information". This expands the "Deep Fetch" to include **following external links** (in descriptions and attachments), **OCR/Multimodal analysis** for image-based documents, and **native support for diverse file formats**.

## Current Limitations
*   **Internal Only:** The system currently only downloads files hosted directly on SAM.gov.
*   **Text-Only Bias:** It struggles with scanned PDFs (images) or complex spreadsheets.
*   **Limited Formats:** Primarily focused on PDF/DOCX; ignores PPTX, XLSX, etc.
*   **No Recursion:** Does not follow links *inside* attachments.

## Proposed Changes

### 1. Upgrade `SamGovAgent` with "Universal Link Follower"
*   **Link Extraction:** Modify `process_detail_page` (or a helper) to parse the *Description* text for URLs.
*   **Filter:** Identify URLs that are likely file hosts (drive.google.com, dropbox.com, box.com, .mil/files).
*   **Action:** Add a method `_process_external_link(url)` to attempt to visit these links using the Playwright session and download visible files.

### 2. Upgrade `AttachmentReaderAgent` (The "Parser Core")
*   **Multimodal OCR:** Leverage Gemini 2.0 Flash Exp's native vision capabilities. Convert PDF pages (if scanned) to images and send to LLM for "Visual OCR", ensuring we catch text in screenshots/diagrams.
*   **Expanded File Support:**
    *   **Excel (`.xlsx`, `.csv`):** Use `pandas` to convert sheets to Markdown tables for specific analysis.
    *   **PowerPoint (`.ppt`, `.pptx`):** Extract text from slides and notes.
    *   **Word (`.docx`, `.doc`):** Continue using text extraction but add "Link Hunting".
*   **Recursive Link Extraction:**
    *   **Logic:** When parsing *any* document, regex scan for URLs.
    *   **Action:** If a URL is found (e.g., "See full specs at [Link]"), trigger a recursive callback to `SamGovAgent` to fetch that link's content, treating it as a new "Virtual Attachment".

### 3. Precision Prompts
*   **Refine Prompt:** Update the system prompt to explicitly command: "Extract ALL specific part numbers, model names, and technical specifications. Do not generalize. If a part number is listed, it must be in the JSON."

# "Quality Crisis” Response (Content Overhaul)

## Goal
To immediately improve the quality of outreach emails by ensuring they contain highly specific, "dense" product information, eliminating vague placeholders like "See Solicitation" or "N/A".

## Changes
1.  **Stop & Fix Campaign:**
    *   Halt the current campaign script.
    *   Update `enrich_and_send_campaign.py` to perform a "Quality Check" before every email.
    *   **Trigger:** If `specifications` is < 20 characters OR `quantity` is 0/1 (generic), FORCE re-analysis.
    *   **Enrichment:** Trigger `AttachmentReaderAgent` with a new "Verbose Mode".

2.  **Verbose Extraction:**
    *   Update `AttachmentReaderAgent` prompt to request a "Detailed technical description. Include dimensions, materials, and usage context. Do not be brief."
    *   Ensure `quantity` inference is aggressive (infer from context if not explicit).

3.  **Dynamic Email Content:**
    *   pass `description`, `delivery_timeline`, `delivery_location` to `format_email_body`.
    *   Update template to display these fields clearly.

## Verification
*   **Dry Run:** Watch the logs of `enrich_and_send_campaign.py`.
*   **Check:** Verify that "Smart Enrichment" triggers for a vague request and results in a detailed email body.

## Verification Plan
1.  **Test Link Following:** Create a mock or find a solicitation with an external link (if possible) or unit test the link extractor regex.
2.  **Test Formats:** Manually add a dummy `.xlsx` and `.pptx` to a solicitation folder and verify `AttachmentReaderAgent` picks them up.
3.  **Test Recursive:** Verify if a link inside a DOCX triggers a fetch.

## System Scaling & Optimization (Phase 3)

### Goal
Scale the pipeline to handle higher volume (10-page batches), extract precise quote requirements, and implement "Deep Outreach" that finds emails directly from supplier websites.

### 1. Scale Ingestion (`main_workflow.py`) [COMPLETE]
*   **Pagination State:** Implemented `keyword_checkpoint.json`.
*   **Batch Size:** Scaled to 10 pages per run.
*   **Ad-Hoc:** Added CLI support for targeted scraping.

### 2. Precise Extraction (`AttachmentReaderAgent.py`) [COMPLETE]
*   **New Field:** Added "Quote Submission Requirements".
*   **Prompt Logic:** asking Gemini for Pricing/Warranty/Delivery breakdown.

### 3. Deep Sourcing & Email Hunting (`ThomasNetAgent.py`) [READY]
*   **Deep Crawl:** `_enrich_supplier_details` visits supplier websites.
*   **Email Extraction:** Scrapes `mailto:` links and text emails.
*   **Pagination:** `batch_sourcing.py` uses `--limit 60`.

### 4. Outreach Logic (`batch_sourcing.py`)
*   **Configuration:** Update subprocess call to `limit=60`.
