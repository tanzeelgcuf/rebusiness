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
from ai_agents.AttachmentReaderAgent.rfq_prompts import PRODUCT_RFQ_PROMPT, SERVICE_RFQ_PROMPT


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

    def _detect_type(self, content_parts):
        """
        Detects if the solicitation is PRODUCT or SERVICE based on keywords.
        Returns "PRODUCT" or "SERVICE".
        """
        full_text = " ".join([str(part)[:10000] for part in content_parts]) # Sample first 10k chars
        full_text_upper = full_text.upper()

        product_score = 0
        service_score = 0

        # PRODUCT Indicators
        product_keywords = ["NSN", "NATIONAL STOCK NUMBER", "CAGE CODE", "PART NUMBER", "DRAWING NUMBER", 
                            "FIRST ARTICLE TESTING", "FAT", "MIL-STD", "ASTM", "FOB ORIGIN", "FOB DESTINATION",
                            "INITIAL PRODUCTION INSPECTION", "IPI", "HARDWARE", "ASSEMBLY"]
        
        # SERVICE Indicators
        service_keywords = ["PERFORMANCE WORK STATEMENT", "PWS", "STATEMENT OF WORK", "SOW", 
                            "MAINTENANCE", "MONITORING", "PLANTING", "ACREAGE", "ACRES", 
                            "LABOR HOUR", "SERVICES", "PERFORMANCE STANDARDS", "SITE PREPARATION"]

        for kw in product_keywords:
            if kw in full_text_upper:
                product_score += 1

        for kw in service_keywords:
            if kw in full_text_upper:
                service_score += 1
        
        print(f"    [Type Detection] Product Score: {product_score}, Service Score: {service_score}")

        if service_score > product_score:
            return "SERVICE"
        elif product_score > service_score:
            return "PRODUCT"
        
        # Tie-breaker logic
        if "PWS" in full_text_upper or "SOW" in full_text_upper:
            return "SERVICE"
        
        return "PRODUCT" # Default to Product if unsure

    def _analyze_content_with_llm(self, content_parts, skip_json=False, strict_fidelity=False, template_type="auto-detect"):
        """
        UPDATED: Now returns structured RFQ markdown with type detection.
        Handles both strings and Gemini file references.
        """
        if not content_parts:
            return {"error": "No content to analyze."}

        # 1. Detect Type
        detected_type = self._detect_type(content_parts)
        final_type = detected_type
        
        if template_type and template_type != "auto-detect":
            final_type = template_type.upper()
            print(f"    [Override] User forced type: {final_type}")
        else:
            print(f"    [Auto-Detect] Solicitation identified as: {final_type}")
        
        # 2. Select Prompt (imported from rfq_prompts)
        if final_type == "PRODUCT":
            system_instruction = PRODUCT_RFQ_PROMPT
        else:
            system_instruction = SERVICE_RFQ_PROMPT
        
        # 3. Prepare Final Prompt with Content
        print(f"    - Generating {final_type} RFQ with Gemini 2.5 Flash...")
        
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # Build message: system instruction + all content
            message_parts = [system_instruction]
            
            for part in content_parts:
                if isinstance(part, str):
                    # Text content
                    message_parts.append(part)
                else:
                    # Gemini file reference
                    message_parts.append(part)
            
            # Generate RFQ
            response = model.generate_content(message_parts)
            rfq_markdown = response.text
            
            # Validate response
            if not rfq_markdown or len(rfq_markdown) < 500:
                print(f"    [Error] LLM response too short ({len(rfq_markdown)} chars).")
                return {"error": "LLM generated incomplete response"}
            
            print(f"    [Success] Generated {len(rfq_markdown)} bytes of RFQ markdown.")
            
            # Return structured result
            return {
                "rfq_content": rfq_markdown,
                "rfq_type": final_type,
                "success": True
            }
            
        except Exception as e:
            print(f"    [Error] LLM generation failed: {e}")
            import traceback
            traceback.print_exc()
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
        if not isinstance(analysis, dict): return analysis
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
        if not isinstance(analysis, dict): return analysis
        contract_id = analysis.get('contract_id') 
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


    def create_summary_report(self, contract_id, skip_json=False, strict_fidelity=False, 
                              template_type="auto-detect", internal_deadline_offset=4, 
                              vendor_email="john@campsable.com", organization_name="Camp Sable, LLC"):
        """
        UPDATED: Comprehensive content assembly ensuring ALL sources are included.
        """
        print(f"\n{'='*80}")
        print(f"STARTING RFQ GENERATION FOR: {contract_id}")
        print(f"{'='*80}\n")
        
        # Get solicitation from database
        solicitation_row = self.db_manager.get_solicitation_by_contract_id(contract_id)
        if not solicitation_row:
            return {"error": f"No solicitation found for contract ID: {contract_id}"}
        
        solicitation = dict(solicitation_row)
        attachments = self.db_manager.get_attachments_for_solicitation(contract_id)
        
        content_parts = []
        processed_paths = set()
        file_count = 0
        
        print(f"[STEP 1] CONTENT ASSEMBLY")
        print(f"-" * 40)
        
        # === PRIORITY 1: Main Description ===
        desc_path = os.path.join(self.config.SOLICITATION_DATA_DIR, contract_id, "description.txt")
        if os.path.exists(desc_path):
            print(f"  [1.1] Processing main description...")
            with open(desc_path, "r", encoding="utf-8") as f:
                full_desc = f.read()
            if full_desc.strip():
                content_parts.append(f"\n=== MAIN SOLICITATION PAGE ===\n{full_desc}")
                processed_paths.add(desc_path)
                file_count += 1
                print(f"        ✓ Added ({len(full_desc)} chars)")
        
        # === PRIORITY 2: Collect ALL Files ===
        all_files = []
        
        # From database
        if attachments:
            print(f"  [1.2] Found {len(attachments)} database attachments")
            for att in attachments:
                att_dict = dict(att)
                path = att_dict['file_path']
                if os.path.exists(path) and path not in processed_paths:
                    all_files.append((path, att_dict['file_name'], 'database'))
        
        # From attachments directory
        attachment_dir = os.path.join(self.config.SOLICITATION_DATA_DIR, contract_id, "attachments")
        if os.path.exists(attachment_dir):
            dir_files = []
            for file in os.listdir(attachment_dir):
                file_path = os.path.join(attachment_dir, file)
                if os.path.isfile(file_path) and file_path not in processed_paths:
                    dir_files.append((file_path, file, 'directory'))
            print(f"  [1.3] Found {len(dir_files)} files in attachments directory")
            all_files.extend(dir_files)
        
        # === PRIORITY 3: Sort by Type ===
        def file_priority(item):
            path, name, source = item
            name_lower = name.lower()
            ext = os.path.splitext(name_lower)[1]
            
            # High priority
            if 'statement' in name_lower and 'work' in name_lower: return 1
            if 'performance' in name_lower and 'work' in name_lower: return 1
            if 'pws' in name_lower or 'sow' in name_lower: return 1
            if 'solicitation' in name_lower and ext == '.pdf': return 2
            if 'attachment' in name_lower and '1' in name_lower: return 3
            if ext == '.pdf': return 4
            if ext == '.docx' or ext == '.doc': return 5
            if ext == '.xlsx' or ext == '.xls': return 6
            if 'external' in name_lower or 'linked' in name_lower: return 7
            if ext == '.txt': return 8
            if ext == '.html': return 9
            return 10
        
        all_files.sort(key=file_priority)
        
        print(f"\n  [1.4] Processing {len(all_files)} files in priority order:")
        print(f"  {'-' * 36}")
        
        # === PRIORITY 4: Process Each File ===
        for idx, (path, name, source) in enumerate(all_files, 1):
            if path in processed_paths:
                continue
            
            print(f"  [{idx:02d}] {name[:50]:<50} ({source})")
            
            try:
                content = self._read_file_content(path)
                
                if content:
                    processed_paths.add(path)
                    file_count += 1
                    
                    # Handle both string and Gemini file references
                    if isinstance(content, str):
                        # Add clear document separator
                        content_parts.append(f"\n\n{'='*80}\n")
                        content_parts.append(f"DOCUMENT: {name}\n")
                        content_parts.append(f"Source: {source}\n")
                        content_parts.append(f"{'='*80}\n\n")
                        content_parts.append(content)
                        print(f"       ✓ Text content ({len(content)} chars)")
                    else:
                        # Gemini file reference (for image-based PDFs)
                        content_parts.append(content)
                        print(f"       ✓ Gemini file reference")
                else:
                    print(f"       ✗ Could not extract content")
                    
            except Exception as e:
                print(f"       ✗ Error: {e}")
        
        print(f"\n  {'='*40}")
        print(f"  TOTAL CONTENT ASSEMBLED:")
        print(f"    - Files processed: {file_count}")
        print(f"    - Content parts: {len(content_parts)}")
        print(f"  {'='*40}\n")
        
        if not content_parts:
            return {"error": "No content could be extracted from solicitation"}
        
        # === STEP 2: Generate RFQ ===
        print(f"[STEP 2] RFQ GENERATION")
        print(f"-" * 40)
        
        result = self._analyze_content_with_llm(
            content_parts,
            skip_json=skip_json,
            strict_fidelity=strict_fidelity,
            template_type=template_type
        )
        
        if "error" in result:
            print(f"  ✗ ERROR: {result['error']}")
            return result
        
        rfq_content = result.get("rfq_content")
        rfq_type = result.get("rfq_type", "UNKNOWN")
        
        # === STEP 3: Post-Processing ===
        print(f"\n[STEP 3] POST-PROCESSING")
        print(f"-" * 40)
        
        # Remove bold formatting
        if "**" in rfq_content:
            print(f"  [3.1] Removing bold formatting...")
            rfq_content = rfq_content.replace("**", "")
            print(f"        ✓ Cleaned")
        
        # Verify no government emails
        gov_email_patterns = ['.mil', '.gov', '@dla.', '@navy.', '@army.', '@usace.']
        found_gov_emails = []
        for pattern in gov_email_patterns:
            if pattern in rfq_content and 'john@campsable.com' not in rfq_content:
                found_gov_emails.append(pattern)
        
        if found_gov_emails:
            print(f"  [3.2] WARNING: Found government email patterns: {found_gov_emails}")
            print(f"        Manual review recommended")
        else:
            print(f"  [3.2] ✓ Email verification passed (only Camp Sable)")
        
        # Verify length
        if len(rfq_content) < 1000:
            print(f"  [3.3] ✗ WARNING: RFQ too short ({len(rfq_content)} chars)")
            print(f"        Expected > 1000 chars. Content may be incomplete.")
        else:
            print(f"  [3.3] ✓ Length check passed ({len(rfq_content)} chars)")
        
        # === STEP 4: Save to Database ===
        print(f"\n[STEP 4] DATABASE STORAGE")
        print(f"-" * 40)
        
        try:
            self.db_manager.add_rfq_output(
                contract_id=contract_id,
                rfq_type=rfq_type,
                rfq_content=rfq_content,
                format=self.config.RFQ_OUTPUT_FORMAT if hasattr(self.config, 'RFQ_OUTPUT_FORMAT') else "markdown"
            )
            print(f"  ✓ Saved to database: {contract_id}")
        except Exception as e:
            print(f"  ✗ Database save failed: {e}")
        
        print(f"\n{'='*80}")
        print(f"RFQ GENERATION COMPLETE")
        print(f"  Type: {rfq_type}")
        print(f"  Size: {len(rfq_content)} characters")
        print(f"  Files processed: {file_count}")
        print(f"{'='*80}\n")
        
        return {
            "rfq_content": rfq_content,
            "rfq_type": rfq_type,
            "files_processed": file_count,
            "success": True
        }

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
