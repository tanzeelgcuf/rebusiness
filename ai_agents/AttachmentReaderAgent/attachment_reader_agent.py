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
                model = genai.GenerativeModel('gemini-2.5-flash-image') # Migrated for higher quota
                response = model.generate_content(prompt)
                return response.text
        except Exception as e:
            print(f"      - Error summarizing chunk: {e}")
            return ""

    def _analyze_content_with_llm(self, content_parts):
        """
        Analyzes content parts (strings or Gemini file objects) with a zero-placeholder policy.
        """
        if not content_parts:
            return {"error": "No content to analyze."}

        system_instruction = """
        You are a MASTER Federal Procurement Analyst. Your mission is to extract ALL information with ZERO placeholders.

        **CRITICAL RULES:**
        1. **Notice ID**: Extract character-perfect (e.g., W912ES26BA007).
        2. **Quantities**: Must be numeric with units (118 EA, not "See Schedule").
        3. **Addresses**: Extract complete Ship-To block (Street, City, State, Zip).
        4. **Calculated Dates**: Convert "30 Days ARO" to specific estimated dates based on today's date.
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
                
                if len(file_refs) > 2:
                    print(f"  Processing {len(file_refs)} documents individually to avoid token limits...")
                    individual_analyses = []
                    for idx, file_ref in enumerate(file_refs):
                        print(f"    Analyzing document {idx+1}/{len(file_refs)}...")
                        message_parts = [system_instruction, f"Analyze this document (part {idx+1} of {len(file_refs)}):", file_ref, formatting_instruction]
                        
                        try:
                            response = model.generate_content(message_parts)
                            if not response.parts:
                                print(f"      - Warning: Empty or blocked response for document {idx+1}")
                                continue
                            doc_analysis = self._extract_json_from_response(response.text)
                            if doc_analysis: individual_analyses.append(doc_analysis)
                        except Exception as e:
                            if "Token count exceeds" in str(e) or "400" in str(e):
                                print(f"      - Document {idx+1} too large for multimodal. Falling back to text chunking...")
                                text_chunks = self._extract_and_chunk_pdf(file_ref)
                                chunk_analyses = []
                                for c_idx, chunk in enumerate(text_chunks):
                                    try:
                                        c_response = model.generate_content([system_instruction, f"Text Chunk {c_idx+1}:", chunk, formatting_instruction])
                                        if c_response.parts:
                                            c_data = self._extract_json_from_response(c_response.text)
                                            if c_data: chunk_analyses.append(c_data)
                                    except: continue
                                if chunk_analyses:
                                    individual_analyses.append(self._merge_analyses(chunk_analyses))
                            else:
                                print(f"      Error analyzing document {idx+1}: {e}")
                    
                    analysis = self._merge_analyses(individual_analyses)
                else:
                    message_parts = [system_instruction]
                    for p in content_parts: message_parts.append(p)
                    message_parts.append(formatting_instruction)
                    response = model.generate_content(message_parts)
                    if response.parts:
                        analysis = self._extract_json_from_response(response.text)
                    else:
                        analysis = {"error": "Empty response from Gemini"}

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
                model = genai.GenerativeModel('gemini-2.5-flash-image')
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
        content_parts.append(f"Solicitation Title: {solicitation.get('title', '')}")
        content_parts.append(f"Solicitation Description:\n{solicitation.get('description', '')}")

        if attachments:
            for i, attachment_row in enumerate(attachments):
                attachment = dict(attachment_row)
                print(f"Processing attachment: {attachment['file_name']}")
                
                content = self._read_file_content(attachment['file_path'])
                
                if content:
                    if isinstance(content, str):
                        content_parts.append(f"\n\n--- Attachment {i+1}: {attachment['file_name']} ---\n{content}")
                    else:
                        # It is a file reference (Gemini Vision)
                        content_parts.append(f"\n\n--- Attachment {i+1}: {attachment['file_name']} (See attached file) ---")
                        # Note: We can't extract links easily from image-only PDF refs unless we OCR first or ask LLM to output them.
                        # We will rely on the LLM to find links in the image text.
                        content_parts.append(content) # Add the file ref object
        
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

        return structured_analysis

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
