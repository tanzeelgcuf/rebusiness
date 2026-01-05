import os
import sys
import tiktoken
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import json
import config
import google.generativeai as genai
import base64
import io
import re
import pandas as pd
import pdfplumber
import requests
import config
from openai import OpenAI
from database_manager import DatabaseManager


class AttachmentReaderAgent:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.config = config
        if config.LLM_PROVIDER == "gemini":
            genai.configure(api_key=config.GEMINI_API_KEY)
        elif config.LLM_PROVIDER == "openai":
            self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoding = None


    def _read_text_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading text file {file_path}: {e}")
            return None

    def _read_pdf_file(self, file_path):
        """
        Reads PDF using pdfplumber for better table/layout extraction.
        Falls back to Gemini Multimodal if file is essentially an image.
        """
        full_text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    # Extract tables first
                    tables = page.extract_tables()
                    if tables:
                        full_text += f"\n--- Page {i+1} Tables ---\n"
                        for table in tables:
                            # Convert list of lists to markdown-like table
                            df = pd.DataFrame(table[1:], columns=table[0]) if len(table) > 1 else pd.DataFrame(table)
                            full_text += df.to_markdown() + "\n\n"
                    
                    # Extract text
                    text = page.extract_text()
                    if text:
                        full_text += f"\n--- Page {i+1} Text ---\n{text}\n"
        except Exception as e:
            print(f"Error reading PDF with pdfplumber: {e}")
        
        # If extraction yielded little text, try Gemini Vision (scanned PDF)
        if len(full_text) < 200 and self.config.LLM_PROVIDER == "gemini":
            try:
                print(f"  [PDF] Low text count ({len(full_text)}). Uploading {file_path} to Gemini Vision...")
                file_ref = genai.upload_file(file_path, mime_type="application/pdf")
                return file_ref
            except Exception as e:
                print(f"  [PDF] Gemini upload failed: {e}")

        return full_text if full_text.strip() else "Could not read PDF content."


    def _read_docx_file(self, file_path):
        try:
            from docx import Document
            document = Document(file_path)
            return "\n".join([para.text for para in document.paragraphs])
        except Exception as e:
            print(f"Error reading DOCX file {file_path}: {e}")
            return None
    
    def _read_xlsx_file(self, file_path):
        try:
            df = pd.read_excel(file_path, sheet_name=None)
            content = ""
            for sheet_name, sheet_df in df.items():
                content += f"--- Sheet: {sheet_name} ---\n"
                content += sheet_df.to_string()
                content += "\n\n"
            return content
        except Exception as e:
            print(f"Error reading XLSX file {file_path}: {e}")
            return None

    def _read_csv_file(self, file_path):
        try:
            df = pd.read_csv(file_path)
            return df.to_string()
        except Exception as e:
            print(f"Error reading CSV file {file_path}: {e}")
            return None

    def _read_pptx_file(self, file_path):
        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            full_text = ""
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        full_text += shape.text + "\n"
            return full_text
        except Exception as e:
            print(f"Error reading PPTX file {file_path}: {e}")
            return None

    def _read_doc_file(self, file_path):
        try:
            import mammoth
            with open(file_path, "rb") as doc_file:
                # mammoth converts .doc to HTML, which is fine for LLM processing
                result = mammoth.convert_to_html(doc_file)
                return result.value
        except Exception as e:
            print(f"Error reading DOC file {file_path} with mammoth: {e}")
            return None

    def _read_file_content(self, file_path):
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None
        _, file_extension = os.path.splitext(file_path)
        file_extension = file_extension.lower()

        if file_extension == '.txt':
            return self._read_text_file(file_path)
        elif file_extension == '.pdf':
            return self._read_pdf_file(file_path)
        elif file_extension == '.docx':
            return self._read_docx_file(file_path)
        elif file_extension == '.doc': # Handle .doc files
            return self._read_doc_file(file_path)
        elif file_extension in ['.xlsx', '.xls']:
            return self._read_xlsx_file(file_path)
        elif file_extension == '.csv':
            return self._read_csv_file(file_path)
        elif file_extension == '.pptx':
            return self._read_pptx_file(file_path)
        else:
            print(f"Unsupported file type for reading: {file_path}")
            return None

    def _get_token_count(self, text):
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # Fallback to character count if tiktoken is not available
            return len(text)

    def _extract_links_from_content(self, text):
        """Extracts http/https URLs from text content."""
        if not text or not isinstance(text, str): return []
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        found = re.findall(url_pattern, text)
        return [f.rstrip('.,;:)') for f in found]

    def _summarize_chunk(self, chunk):
        """Summarizes a chunk of text, focusing on retaining all product and location details."""
        print(f"    - Summarizing chunk of {self._get_token_count(chunk)} tokens...")
        prompt = f"""
        Please summarize the following text from a government solicitation document. **It is critical to retain all specific details about products, services, and required locations.** This includes exact product names, quantities, part numbers, specifications (materials, dimensions, standards), and precise delivery or performance addresses. Do not generalize these details.

        Text to summarize:
        ---
        {chunk}
        ---

        Provide a concise summary that preserves all key product, service, and location details.
        """
        try:
            if self.config.LLM_PROVIDER == "openai":
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500
                )
                return response.choices[0].message.content
            else: # Default to gemini
                model = genai.GenerativeModel('gemini-2.5-flash') 
                response = model.generate_content(prompt)
                return response.text
        except Exception as e:
            print(f"      - Error summarizing chunk: {e}")
            return ""

    def _analyze_content_with_llm(self, content_parts):
        """
        Analyzes content parts (strings or Gemini file objects) with template-specific extraction.
        """
        if not content_parts:
            return {"error": "No content to analyze."}

        system_instruction = """You are a MASTER Federal Procurement Analyst extracting data for vendor RFQ emails.

**CRITICAL: TEMPLATE CLASSIFICATION**
First, determine if this is PRODUCT or SERVICE:
- PRODUCT indicators: NSN, CAGE code, Part Number, physical items for SALE, equipment procurement, "supply", packaging specs ONLY.
- SERVICE/MAINTENANCE indicators: PWS, SOW, "REPAIR", "OVERHAUL", "MAINTENANCE", "MODIFICATION", labor categories, site locations, "planting", "landscape", "acres".
- **IMPORTANT**: If the solicitation is for REPAIR or MAINTENANCE of an item (even if it has an NSN), classify it as SERVICE to match the Services template.

**ZERO PLACEHOLDER POLICY & INFERENCES:**
- NEVER use "See solicitation", "N/A", "Contact CO", "Not specified".
- Extract from ALL documents (main page, PDFs, Excel, Word, linked pages).
- **Total Work Area**: If not acreage-based (e.g., Repair), use "N/A - Technical Service (Repair of {Quantity} Units)". NEVER output "0 acres" for non-landscaping tasks.
- **Work Locations**: If not a site-based service (like landscaping), use "Contractor's Facility (TBD at Award)".
- **Insurance**: If no specific limits are found, use "Standard Commercial Liability as per FAR Part 28 (General, Auto, Workers Comp)".
- **Wage Determination**: If no specific WD number is found, use "Federal Contractor Standards (SCA or Walsh-Healey as applicable)".
- **For Delivery Frequency**, search for "Induction", "Monthly", "As required", "Upon receipt of carcass".
- **For Specifications**, extract specific identifiers like "MIL-STD-####", "MIL-PRF-####", "ISO 9001", "Drawing No.", or "TDP".
- Only use "Information not provided in solicitation" if truly absent after exhaustive search across all files, but prefer descriptive inferences for the fields above.

**MANDATORY FIELD FILLING (NO EXCEPTIONS):**
1. **Ship-To Address**: If NO explicit delivery address is found, you MUST use the agency's physical location (from the overview) as the "Ship To". DO NOT output "Information not provided". 
2. **CLIN Quantity**: If not listed, ALWAYS use "1" and "LOT" (or "EA") for the first CLIN.
3. **Manufacturer/Part Number**: If description mentions a part, extract it. If not found, use "TBD per Specifications".
4. **NSN**: If not found and part is available, use "N/A (See Part Number)".


**ZERO PLACEHOLDER POLICY:**
- NEVER use "See solicitation", "N/A", "Contact CO"
- Extract from ALL documents (main page, PDFs, Excel, Word, linked pages)
- Only use "Information not provided in solicitation" if truly absent after exhaustive search

**HANDLING FAILED LINK ACCESS:**
If you see files named "FAILED_ACCESS_*.txt", these are links that could not be accessed due to firewalls or authentication.
For missing data from failed links, use these INFERENCE STRATEGIES:

1. **Agency Address**: Infer from agency name
   - "DEPT OF THE NAVY, NAVSUP WSS MECHANICSBURG" → "NAVSUP Weapon Systems Support, 5450 Carlisle Pike, Mechanicsburg, PA 17055"
   - "DLA Distribution" → "Defense Logistics Agency, 8725 John J. Kingman Road, Fort Belvoir, VA 22060"
   - Look for city/state in agency name and construct standard military address format

2. **Ship-To Address**: Extract from delivery clauses or infer from agency
   - Check for "FOB Destination" clauses with addresses
   - Look in CLIN descriptions for delivery locations
   - Use agency address as fallback if no other info

3. **NSN (National Stock Number)**: Look for patterns
   - Format: ####-##-###-#### (13 digits with dashes)
   - Often in title, description, or CLIN details
   - May be labeled as "NSN:", "Stock Number:", or just the number

4. **CAGE Code**: Extract from manufacturer info
   - 5-character alphanumeric code
   - Look for "CAGE:", "Manufacturer Code:", or near part numbers
   - Check solicitation number patterns

5. **Quantities & Units**: Parse from tables and text
   - Look for numeric patterns with units (EA, LB, SET, LOT)
   - Check CLIN tables, schedules, or line items
   - Parse "118 each" → quantity: 118, unit: "EA"

7. **MULTI-DOCUMENT SYNTHESIS (CRITICAL)**:
   - You will receive a base solicitation AND amendments (0001, 0002, etc.).
   - Amendments often only extend due dates or change minor clauses.
   - **DO NOT** let a short amendment description replace the detailed technical specifications and CLIN tables from the base solicitation.
   - Combine all info. If an amendment changes a date, use the NEW date. If it doesn't mention something, keep the info from the previous/base version.

8. **REPAIR/MODIFICATION CONTRACTS (Special Handling)**:
   - If description mentions "Repair", "Overhaul", or "Modification":
   - **Quantity**: Often "1 LOT", "1 SV" (Service), or "AS GEN" (As Generated). **DO NOT** leave blank. Use "1 LOT" if unsure.
   - **Unit**: Use "LOT" or "SV" if not "EA".
   - **CLINs**: If no clear CLIN table exists, infer a CLIN "0001" for the main service/repair item.

9. **CLIN TABLE EXTRACTION**:
   - Look for Sub-Line Items (SLINs) like 0001AA, 0001AB.
   - Extract quantities for EVERY CLIN/SLIN found.
   - If quantities are in a table but descriptions are elsewhere, join them.
   - **QUALITY**: Extract "Quality Level", "Inspection Point", and "Acceptance Point" for each CLIN.

10. **MISSING ADDRESS FALLBACK**:
   - If "Ship To" is strictly not found, look for "Administered By" or "Issued By".
   - Use that address but prepend "Note: Verify exact delivery location. Administered by: ".


**FOR PRODUCTS - Extract to match Claude Vendor List.odt:**
{
  "solicitation_type": "PRODUCT",
  "notice_id": "EXACT match from SAM.gov (e.g., W912ES26BA007)",
  "title": "Full solicitation title",
  "overview": {
    "agency_name": "Full agency name",
    "agency_address": "Complete mailing address with all lines (INFER if needed)",
    "contract_type": "Firm Fixed Price / Cost-Plus / T&M",
    "set_aside": "Small Business / WOSB / HUBZone / 8(a) / Unrestricted",
    "solicitation_date": "YYYY-MM-DD",
    "quotes_due": "YYYY-MM-DD HH:MM TZ",
    "naics_code": "######",
    "naics_description": "Industry description",
    "size_standard": "### employees or $##.# million"
  },
  "specifications": {
    "manufacturer_cage": "5-character code (SEARCH THOROUGHLY)",
    "manufacturer_part_number": "Exact part number",
    "nsn": "####-##-###-#### format (SEARCH THOROUGHLY)",
    "description": "Complete technical description"
  },
  "clins": [
    {
      "clin": "0011",
      "description": "1st Year -- Item description",
      "quantity": 118,
      "unit": "EA",
      "type": "FFP",
      "inspection_point": "Origin",
      "acceptance_point": "Origin",
      "quality_level": "Military, Level B",
      "packaging": "MIL-STD-2073-1",
      "notes": "Guaranteed Minimum Award Quantity"
    }
  ],
  "delivery_requirements": {
    "fob_point": "Destination",
    "ship_to_address": {
      "organization": "DLA Weapons Support",
      "street": "6501 East Eleven Mile Road",
      "city": "Warren",
      "state": "MI",
      "zip": "48397-5000"
    },
    "lead_time_days": 340,
    "delivery_frequency": "24 units every 30 days",
    "calculated_first_delivery": "2027-01-07"
  },
  "submission": {
    "method": "Email",
    "email": "john.doe@agency.mil",
    "due_date": "YYYY-MM-DD HH:MM TZ",
    "required_forms": ["SF 1449", "Bid Bond"],
    "evaluation_basis": "LPTA"
  }
}

**FOR SERVICES - Extract to match Claude Services List.odt:**
{
  "solicitation_type": "SERVICE",
  "notice_id": "EXACT match from SAM.gov",
  "project_title": "Full project title",
  "project_summary": {
    "contract_type": "3-Year Service Contract",
    "purpose": "High-level objective",
    "total_work_area": {
      "base_acres": 165.4,
      "option_acres": 10.4
    },
    "work_locations": [
      {
        "site_id": "8A",
        "county": "Clay",
        "state": "MN",
        "acreage": 28.8,
        "description": "Floodplain & Savanna"
      }
    ]
  },
  "scope_categories": [
    {
      "category": "Forest Establishment",
      "description": "Develop planting and maintenance plans"
    }
  ],
  "timeline": {
    "periods": [
      {
        "year": "Year 1",
        "date_range": "Award → 31 Dec 2026",
        "activities": ["Site prep", "Planting", "Maintenance"]
      }
    ],
    "deliverables": [
      {
        "name": "Project Schedule",
        "due_days": 15,
        "format": "Excel or PDF"
      }
    ]
  },
  "compliance": {
    "key_requirements": ["Safety Plan", "Permits", "Licensed applicators"],
    "insurance": {
      "general_liability": "$1,000,000",
      "auto_liability": "$1,000,000",
      "workers_comp": "As required by state law"
    },
    "wage_determination": "SCA compliance required"
  },
  "submission": {
    "method": "Email / Hand-carry / Mail",
    "address": "Complete mailing address",
    "due_date": "YYYY-MM-DD HH:MM TZ",
    "required_documents": ["SF 1449", "Capability Statement"]
  }
}
"""
        
        formatting_instruction = """
        Ensure INVALID or MISSING data is explicitly marked as "Not specified in solicitation" ONLY after thorough cross-referencing.
        """

        try:
            analysis = {}
            if self.config.LLM_PROVIDER == "openai":
                combined_text = "\n\n".join([str(p) for p in content_parts if isinstance(p, str)])
                
                # Check for token limits (TPM)
                if len(combined_text) > 40000: # ~60k tokens
                    print(f"  Warning: Text too large for single OpenAI call ({len(combined_text)} chars). Chunking...")
                    text_chunks = [combined_text[i:i + 35000] for i in range(0, len(combined_text), 35000)]
                    chunk_analyses = []
                    for idx, chunk in enumerate(text_chunks):
                        print(f"    Analyzing text chunk {idx+1}/{len(text_chunks)}...")
                        if idx > 0:
                            import time
                            print(f"      Waiting 20 seconds for rate limits...")
                            time.sleep(20)
                        prompt = f"{system_instruction}\n\nDocument Content (Part {idx+1}):\n{chunk}\n\n{formatting_instruction}"
                        try:
                            response = self.openai_client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{"role": "user", "content": prompt}],
                                response_format={"type": "json_object"},
                                max_tokens=4000
                            )
                            chunk_data = json.loads(response.choices[0].message.content)
                            if chunk_data: chunk_analyses.append(chunk_data)
                        except Exception as e:
                            print(f"      Error in OpenAI chunk {idx+1}: {e}")
                    analysis = self._merge_analyses(chunk_analyses)
                else:
                    prompt = f"{system_instruction}\n\nDocument Content:\n{combined_text}\n\n{formatting_instruction}"
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini", 
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                        max_tokens=4000
                    )
                    analysis = json.loads(response.choices[0].message.content)

            else: # Gemini
                model = genai.GenerativeModel('gemini-2.5-flash-image')
                file_refs = [p for p in content_parts if not isinstance(p, str)]
                
                if len(file_refs) > 5:
                    print(f"  Processing {len(file_refs)} documents individually to avoid total token limits...")
                    individual_analyses = []
                    for idx, file_ref in enumerate(file_refs):
                        print(f"    Analyzing document {idx+1}/{len(file_refs)}...")
                        message_parts = [system_instruction, f"Analyze this document (part {idx+1} of {len(file_refs)}):", file_ref, formatting_instruction]
                        
                        try:
                            # Use Pro for better instruction following on complex synthesis
                            pro_model = genai.GenerativeModel('gemini-2.5-pro')
                            response = pro_model.generate_content(message_parts)
                            if response.candidates and response.candidates[0].content.parts:
                                doc_analysis = self._extract_json_from_response(response.text)
                                if doc_analysis: individual_analyses.append(doc_analysis)
                            else:
                                print(f"      - Warning: Empty or blocked response for document {idx+1}")
                        except Exception as e:
                            print(f"      Error analyzing document {idx+1}: {e}")
                    
                    analysis = self._merge_analyses(individual_analyses)
                else:
                    print(f"  Collective analysis of {len(content_parts)} items...")
                    message_parts = [system_instruction]
                    for idx, p in enumerate(content_parts):
                        if isinstance(p, str):
                            print(f"    - Part {idx} (Text): {len(p)} characters")
                        else:
                            print(f"    - Part {idx} (File Object): {p.display_name}")
                        message_parts.append(p)
                    message_parts.append(formatting_instruction)
                    
                    try:
                        # Use Pro for collective analysis (better long-context synthesis)
                        pro_model = genai.GenerativeModel('gemini-2.5-pro')
                        print("  [LLM] Calling Gemini 2.5 Pro...")
                        response = pro_model.generate_content(message_parts)
                        
                        if response.candidates and response.candidates[0].content.parts:
                            raw_response = response.text
                            print(f"  [LLM] Received response ({len(raw_response)} characters)")
                            analysis = self._extract_json_from_response(raw_response)
                            if not analysis:
                                 print(f"    [!] Failed to extract JSON from response. Raw response head: {raw_response[:500]}")
                        else:
                            print(f"  [LLM] No candidates or parts in response. Safety settings or blocking?")
                            analysis = {"error": "Empty or blocked response from Gemini"}
                    except Exception as e:
                        print(f"    [!] Gemini call failed: {e}")
                        analysis = {"error": str(e)}

            return analysis
        except Exception as e:
            print(f"Error during LLM analysis: {e}")
            return {"error": str(e)}

    def _extract_json_from_response(self, text):
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return json.loads(text)
        except:
            return None

    def _extract_and_chunk_pdf(self, file_ref, chunk_size=15000):
        filename = getattr(file_ref, 'display_name', os.path.basename(str(file_ref)))
        local_path = os.path.join("downloads", filename)
        if not os.path.exists(local_path): return []
        full_text = ""
        try:
            with pdfplumber.open(local_path) as pdf:
                for page in pdf.pages: full_text += (page.extract_text() or "") + "\n"
        except: return []
        return [full_text[i:i + chunk_size + 2000] for i in range(0, len(full_text), chunk_size)]

    def _validate_completeness(self, analysis):
        """
        Checks for missing critical fields and triggers Deep Research.
        """
        critical_missing = []
        
        # Check Ship-To
        dr = analysis.get('delivery_requirements', {})
        if not dr.get('ship_to_address') or "solicitation" in str(dr.get('ship_to_address')).lower():
            critical_missing.append("Ship-To Address")
            
        # Check CLINs
        if not analysis.get('clins') or len(analysis.get('clins')) == 0:
            critical_missing.append("CLIN Table")
            
        if critical_missing:
            print(f"  [Validation] Missing critical data: {critical_missing}. Triggering Deep Research...")
            analysis = self._research_missing_data(analysis)
            
        return analysis

    def _merge_analyses(self, analyses):
        if not analyses: return {}
        if len(analyses) == 1: return analyses[0]
        merged = analyses[0].copy()
        
        def is_p(x):
            if not x: return True
            s = str(x).lower()
            return any(p in s for p in ["information not available", "see solicitation", "contact co", "n/a", "not_found", "none", "{}"])

        for analysis in analyses[1:]:
            for key, value in analysis.items():
                curr = merged.get(key)
                if is_p(curr) and not is_p(value):
                    merged[key] = value
                elif isinstance(value, list) and isinstance(curr, list):
                    merged[key].extend([v for v in value if v not in curr])
                elif isinstance(value, dict) and isinstance(curr, dict):
                    for dk, dv in value.items():
                        if is_p(merged[key].get(dk)) and not is_p(dv):
                            merged[key][dk] = dv
                elif not is_p(value):
                    merged[key] = value
        return merged

    def _research_missing_data(self, analysis):
        """
        Uses SerpAPI to find missing insurance, wage, or security data.
        """
        contract_id = analysis.get('contract_id') # This might be the hex ID
        title = analysis.get('title', '')
        agency = analysis.get('soliciting_entity', '')
        
        # Use a more searchable ID if available
        search_id = contract_id
        if len(str(contract_id)) > 20: # Likely a hex ID
             # Try to find a real notice ID in the summary or checklist
             id_match = re.search(r'([A-Z0-9-]{6,20})', str(analysis.get('summary', '')))
             if id_match: search_id = id_match.group(1)

        def is_p(x):
            if not x: return True
            s = str(x).lower()
            return any(p in s for p in ["information not available", "see solicitation", "n/a", "none", "{}"])

        # Target 1: Insurance
        insurance = analysis.get('insurance_requirements', {})
        if is_p(insurance.get('general_liability')) or is_p(insurance.get('workers_compensation')):
            print(f"  Searching for missing insurance data for {title}...")
            query = f"insurance requirements federal contract {agency} {title} {search_id} FAR 52.228-5 limits"
            res = self._call_serpapi(query)
            if res:
                prompt = f"Extract specific insurance liability limits (dollar amounts) from these search results for {title}. Context: {res}\nReturn JSON: {{'general_liability': '...', 'auto_liability': '...', 'workers_compensation': '...'}}"
                ext = self._get_simple_json_from_llm(prompt)
                if ext:
                    for k, v in ext.items():
                        if not is_p(v): 
                             if 'insurance_requirements' not in analysis: analysis['insurance_requirements'] = {}
                             analysis['insurance_requirements'][k] = v

        # Target 2: Wages
        wages = analysis.get('wage_labor_requirements', {})
        wd_number = wages.get('wage_determination')
        if is_p(wd_number) or "Information not available" in str(wd_number):
            print(f"  Searching for Wage Determination for {title}...")
            query = f"wage determination for {agency} contract {title} {search_id}"
            res = self._call_serpapi(query)
            if res:
                prompt = f"Identify the Wage Determination (WD) number (e.g. 2015-4191) and primary technician labor rates from these search results. Context: {res}\nReturn JSON: {{'wage_determination': '...', 'sample_rates': '...'}}"
                ext = self._get_simple_json_from_llm(prompt)
                if ext: 
                    if 'wage_labor_requirements' not in analysis: analysis['wage_labor_requirements'] = {}
                    analysis['wage_labor_requirements']['wage_determination'] = f"{ext.get('wage_determination')} - {ext.get('sample_rates')}"

        # Target 3: NSN (if missing)
        specs = analysis.get('specifications', {})
        nsn = specs.get('nsn', '')
        cage = specs.get('manufacturer_cage', '')
        part = specs.get('manufacturer_part_number', '')
        
        if is_p(nsn) and (cage and not is_p(cage)) and (part and not is_p(part)):
             print(f"  Searching for missing NSN for CAGE {cage} Part {part}...")
             query = f"NSN for CAGE {cage} Part Number {part}"
             res = self._call_serpapi(query)
             if res:
                 prompt = f"Identify the National Stock Number (NSN) (13 digit number, often format xxxx-xx-xxx-xxxx) for Part Number {part} and CAGE {cage} from these search results. Context: {res}\nReturn JSON: {{'nsn': '...'}}"
                 ext = self._get_simple_json_from_llm(prompt)
                 if ext and ext.get('nsn') and not is_p(ext.get('nsn')):
                     print(f"  Found NSN: {ext.get('nsn')}")
                     analysis['specifications']['nsn'] = ext.get('nsn')
                 else:
                     # Fallback if search fails but we have part number
                     analysis['specifications']['nsn'] = f"N/A (See Part Number {part})"

        return analysis

    def _get_simple_json_from_llm(self, prompt):
        try:
            if self.config.LLM_PROVIDER == "openai":
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                return json.loads(response.choices[0].message.content)
            else:
                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content(prompt)
                return self._extract_json_from_response(response.text)
        except: return None

    def _call_serpapi(self, query):
        if not hasattr(config, 'SERPAPI_KEY') or not config.SERPAPI_KEY: return None
        url = "https://serpapi.com/search"
        params = {"q": query, "api_key": config.SERPAPI_KEY, "engine": "google", "num": 5}
        try:
            resp = requests.get(url, params=params)
            data = resp.json()
            results = []
            for r in data.get('organic_results', []):
                results.append(f"Title: {r.get('title')}\nSnippet: {r.get('snippet')}")
            return "\n\n".join(results)
        except: return None


    def create_summary_report(self, contract_id):
        solicitation_row = self.db_manager.get_solicitation_by_contract_id(contract_id)
        if not solicitation_row:
            return {"error": f"No solicitation found for contract ID: {contract_id}"}
        solicitation = dict(solicitation_row)

        attachments = self.db_manager.get_attachments_for_solicitation(contract_id)
        
        content_parts = []
        processed_paths = set()
        
        # 1. Start with the most important: Full description from disk
        desc_path = os.path.join(self.config.SOLICITATION_DATA_DIR, contract_id, "description.txt")
        if os.path.exists(desc_path):
            with open(desc_path, "r", encoding="utf-8") as f:
                full_desc = f.read()
            if full_desc.strip():
                content_parts.append(f"Solicitation Description (Primary Source):\n{full_desc}")
                processed_paths.add(desc_path)
                print(f"  [Content] Added full description ({len(full_desc)} bytes)")
        else:
            content_parts.append(f"Solicitation Summary:\n{solicitation.get('description', '')}")

        # 2. Collect ALL available attachments (DB + Disk)
        all_files = [] # list of (path, name, type)
        
        # From DB
        if attachments:
            for att in attachments:
                att_dict = dict(att)
                path = att_dict['file_path']
                if os.path.exists(path):
                    all_files.append((path, att_dict['file_name'], 'attachment'))
        
        # From Disk Scan (Deep Crawl)
        deep_crawl_dir = os.path.join(self.config.SOLICITATION_DATA_DIR, contract_id, "attachments")
        if os.path.exists(deep_crawl_dir):
            for file in os.listdir(deep_crawl_dir):
                file_path = os.path.join(deep_crawl_dir, file)
                if file_path not in processed_paths:
                    all_files.append((file_path, file, 'deep_crawl'))

        # 3. Sort files by priority: PDF > DOCX > XLSX > Text Portals > Others
        def priority_score(item):
            path, name, source = item
            ext = os.path.splitext(name.lower())[1]
            if ext == '.pdf': return 1
            if ext == '.docx': return 2
            if ext == '.xlsx': return 3
            if 'linked_page' in name.lower(): return 4
            return 5
            
        all_files.sort(key=priority_score)
        
        # 4. Process files with duplication check
        for path, name, source in all_files:
            if path in processed_paths: continue
            
            print(f"  [Content] Processing: {name} ({source})")
            content = self._read_file_content(path)
            
            if content:
                processed_paths.add(path)
                header = f"\n\n--- Source: {name} ({source}) ---"
                
                if isinstance(content, str):
                    # Truncate generic portal pages if they are too long to save tokens
                    if 'linked_page' in name.lower() and len(content) > 10000:
                         content = content[:10000] + "\n... (truncated)"
                    
                    content_parts.append(f"{header}\n{content}")
                else:
                    # Gemini file object (Vision)
                    content_parts.append(header)
                    content_parts.append(content)

        # Analyze with LLM
        structured_analysis = self._analyze_content_with_llm(content_parts)
        
        # Enrich with Web Research if critical data is missing
        if "error" not in structured_analysis:
            structured_analysis['contract_id'] = contract_id # Ensure CID is there for research
            structured_analysis = self._research_missing_data(structured_analysis)

        # Robust handling: Ensure it is a dict

        # Robust handling: Ensure it is a dict
        if isinstance(structured_analysis, list):
            if structured_analysis and isinstance(structured_analysis[0], dict):
                 # Maybe the LLM returned a list of products? Try to salvage.
                 # Or it returned [ { "soliciting_entity": ... } ]
                 structured_analysis = structured_analysis[0]
            else:
                 structured_analysis = {"error": "LLM returned unexpected list format", "raw": structured_analysis}
        
        if not isinstance(structured_analysis, dict):
             structured_analysis = {"error": "LLM returned invald format"}

        # Post-Processing: Extract links from text parts (redundancy check)
        text_only_content = "\n".join([str(p) for p in content_parts if isinstance(p, str)])
        regex_links = self._extract_links_from_content(text_only_content)
        
        # Merge LLM found links with Regex links
        llm_links = structured_analysis.get('external_resource_links', [])
        all_links = list(set(regex_links + llm_links))
        
        # Filter junk links
        clean_links = [l for l in all_links if len(l) > 10 and not any(x in l for x in ['google.com/search', 'facebook.com', 'w3.org'])]
        structured_analysis['external_resource_links'] = clean_links


        # Add solicitation-level info to the analysis
        structured_analysis['contract_id'] = contract_id
        structured_analysis['title'] = solicitation.get('title')
        structured_analysis['url'] = solicitation.get('url')

        # --- SAVE EXTRACTED PRODUCTS TO DB ---
        if 'product_details' in structured_analysis and isinstance(structured_analysis['product_details'], list):
            print(f"Extracting {len(structured_analysis['product_details'])} products to database...")
            for prod in structured_analysis['product_details']:
                try:
                    # Flatten specifications if it's a list
                    specs = prod.get('specifications', [])
                    if not isinstance(specs, list):
                        specs = [str(specs)] if specs else []

                    # Add Part Number to specs if present
                    part_num = prod.get('part_number', '')
                    if part_num and str(part_num).lower() not in ['n/a', 'none', 'unknown']:
                        specs.insert(0, f"Part Number: {part_num}")

                    specs_str = "; ".join(specs)

                    # Extract quantity safely
                    qty = prod.get('quantity', 0)
                    try:
                        qty = int(float(str(qty).replace(',', '').strip()))
                    except:
                        qty = 0

                    self.db_manager.add_product(
                        contract_id=contract_id,
                        product_name=prod.get('name', 'Unknown Product'),
                        description=prod.get('description', ''),
                        specifications=specs_str,
                        quantity=qty
                    )
                except Exception as e:
                    print(f"Failed to save product {prod.get('name')}: {e}")

        # Determine review status
        review_status, review_notes = self._determine_review_status(structured_analysis)
        if review_status == 'flagged':
            print(f"  [!] Solicitation flagged for manual review: {review_notes}")
        
        # Save analysis with status
        json_str = json.dumps(structured_analysis)
        self.db_manager.add_solicitation_analysis(
            contract_id=contract_id, 
            analysis_summary=json_str,
            confidence=0.9 if review_status == 'reviewed' else 0.5,
            review_status=review_status
        )
        self.db_manager.update_solicitation_data(contract_id, json_str) # Sync data column

        return structured_analysis

    def _determine_review_status(self, analysis):
        """Checks for missing critical information to flag for review."""
        missing = []
        
        # 1. Product identifier check
        specs = analysis.get('specifications', {})
        cage = specs.get('manufacturer_cage', '')
        part = specs.get('manufacturer_part_number', '')
        nsn = specs.get('nsn', '')
        
        sol_type = analysis.get('solicitation_type', 'PRODUCT')
        if sol_type == 'PRODUCT':
            if (not cage or "Information not provided" in cage) and \
               (not part or "Information not provided" in part) and \
               (not nsn or "Information not provided" in nsn):
                missing.append("No Product Identifiers (CAGE/PN/NSN)")

        # 2. Delivery Address check
        delivery = analysis.get('delivery_requirements', {})
        ship_to = delivery.get('ship_to_address', {})
        if isinstance(ship_to, dict):
            if "Information not provided" in ship_to.get('city', '') and \
               "Information not provided" in ship_to.get('state', ''):
                missing.append("Ship-To Address")
        elif "Information not provided" in str(ship_to):
             missing.append("Ship-To Address")

        # 3. Deadline check
        sub = analysis.get('submission', {})
        if "Information not provided" in sub.get('due_date', ''): missing.append("Due Date")

        if missing:
            return 'flagged', ", ".join(missing)
        return 'reviewed', "Complete"

if __name__ == "__main__":
    db_manager = DatabaseManager()
    
    # Get all solicitations that don't have an analysis yet
    conn = db_manager._connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.contract_id FROM solicitations s
        LEFT JOIN solicitation_analysis sa ON s.contract_id = sa.contract_id
        WHERE sa.analysis_json IS NULL
    """)
    solicitations_to_process = [row[0] for row in cursor.fetchall()]
    db_manager._close_db()

    if not solicitations_to_process:
        print("No new solicitations to analyze.")
    else:
        print(f"Found {len(solicitations_to_process)} solicitations to analyze.")
        reader_agent = AttachmentReaderAgent()
        for contract_id in solicitations_to_process:
            print(f"---\n--- Generating structured analysis for solicitation: {contract_id} ---")
            
            structured_analysis = reader_agent.create_summary_report(contract_id)
            
            if "error" not in structured_analysis:
                # Save the analysis to the database
                db_manager.add_solicitation_analysis(contract_id, json.dumps(structured_analysis))
                print(f"Successfully saved structured analysis for {contract_id} to database.")
                # Print the structured analysis
                print(json.dumps(structured_analysis, indent=2))
            else:
                print(f"Error generating analysis for {contract_id}: {structured_analysis['error']}")
            
            print("\n" + "=" * 80 + "\n")
