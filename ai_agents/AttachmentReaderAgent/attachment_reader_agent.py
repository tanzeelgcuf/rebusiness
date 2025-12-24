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
import PyPDF2
import re
from openai import OpenAI # Import OpenAI client
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
        if self.config.LLM_PROVIDER == "gemini":
            try:
                print(f"Uploading {file_path} to Gemini for Multimodal processing...")
                file_ref = genai.upload_file(file_path, mime_type="application/pdf")
                return file_ref
            except Exception as e:
                print(f"Error uploading PDF to Gemini: {e}")
                return "Error processing PDF."
        
        # Fallback for OpenAI or if upload fails (though we want consistency)
        full_text = ""
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page_num in range(len(reader.pages)):
                    full_text += reader.pages[page_num].extract_text()
        except Exception as e:
            print(f"Error reading PDF file {file_path} with PyPDF2: {e}")
        return full_text if full_text.strip() else "Could not read content or content is empty."

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
                model = genai.GenerativeModel('gemini-2.0-flash-exp') # Corrected model name
                response = model.generate_content(prompt)
                return response.text
        except Exception as e:
            print(f"      - Error summarizing chunk: {e}")
            return ""

    def _analyze_content_with_llm(self, content_parts):
        """
        Analyzes content parts (strings or Gemini file objects).
        """
        if not content_parts:
            return {"error": "No content to analyze."}

        # prompt_v3 definition (kept the same logic, extracted for clarity)
        system_instruction = """
        As an expert government contract analyst, your task is to meticulously review the provided solicitation documents and extract key information into a structured JSON format. 
        
        The inputs may include text descriptions and attached PDF/Image documents. **You must strictly extract product details from ALL provided sources, especially the attachments.**
        
        **CRITICAL**: When extracting product specifications, look for:
        - Exact Size/Specs
        - Material Composition
        - Part Numbers
        - Quantities (Search explicitly for "Qty", "Quantity", "Units". If "Market Research", look for "Est. Qty". If implied like "Replacement of X", qty is 1.)
        """
        
        formatting_instruction = """
        Based on the content, extract the following details into a valid JSON object:

        1.  **soliciting_entity**: Full name of the organization.
        2.  **soliciting_contact_info**: {email, phone}.
        3.  **product_details**: A list of objects. Each object must have:
            *   `line_item_number`: (e.g., CLIN 0001)
            *   `name`: Name of the product (Extracted exactly).
            *   `description`: Detailed technical description. Include dimensions, materials, and usage context. Do not be brief.
            *   `quantity`: Numerical quantity (integer). If implied (e.g. "1 unit"), separate the number. If range, provide max.
            *   `unit`: Unit of measure (e.g., "EA").
            *   `part_number`: EXACT Part Number, NSN, or Model Number. Do not hallucinate.
            *   `specifications`: A detailed list of technical specs, materials, dimensions. **Capture ALL specs found.**
        4.  **delivery_location**: {street, city, state, zip_code}. If multiple, list primary.
        5.  **delivery_timeline**: Specific dates, duration (e.g. "30 days ARO"), or period of performance found.
        6.  **summary**: A detailed summary (2-4 sentences).
        7.  **external_resource_links**: A list of ANY URLs found in the documents that likely contain technical data (Dropbox, Drive, Portals).
        
        Return strictly valid JSON.

        Return strictly valid JSON.
        """

        try:
            analysis = {}
            if self.config.LLM_PROVIDER == "openai":
                # OpenAI doesn't support the 'file_ref' object from Gemini, so we assume all parts are strings here
                # (Fallback logic in _read_pdf_file handles string conversion for OpenAI)
                combined_text = "\n\n".join([str(p) for p in content_parts if isinstance(p, str)])
                
                # ... (OpenAI limits handling omitted for brevity, assuming similar split logic if needed, 
                # but for now simplicity to match structure) ...
                
                prompt = f"{system_instruction}\n\nDocument Content:\n{combined_text}\n\n{formatting_instruction}"

                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo", 
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    max_tokens=4000
                )
                analysis = json.loads(response.choices[0].message.content)

            else: # Gemini
                model = genai.GenerativeModel('gemini-2.0-flash-exp', generation_config={"response_mime_type": "application/json"})
                
                # Construct message parts
                message_parts = [system_instruction]
                for part in content_parts:
                    if isinstance(part, str):
                        message_parts.append(part)
                    else:
                        # It's a file reference
                        message_parts.append("Refer to the following document attachment:")
                        message_parts.append(part)
                
                message_parts.append(formatting_instruction)

                response = None
                max_retries = 3
                import time
                for attempt in range(max_retries):
                    try:
                        response = model.generate_content(message_parts)
                        analysis = json.loads(response.text)
                        break
                    except Exception as e:
                        if "429" in str(e) and attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 30
                            print(f"      - Rate limit hit (429). Retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            raise e

            return analysis

        except Exception as e:
            print(f"Error during LLM analysis: {e}")
            return {"error": f"LLM analysis failed: {e}"}

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
                        content_parts.append(f"\n\n--- Attachment {i+1}: {attachment['file_name']} (See attached file) ---")
                        # Note: We can't extract links easily from image-only PDF refs unless we OCR first or ask LLM to output them.
                        # We will rely on the LLM to find links in the image text.
                        content_parts.append(content) # Add the file ref object
        
        # Analyze with LLM
        structured_analysis = self._analyze_content_with_llm(content_parts)

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
