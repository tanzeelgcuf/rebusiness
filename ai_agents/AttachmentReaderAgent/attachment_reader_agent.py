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
                model = genai.GenerativeModel('gemini-2.5-pro') # Corrected model name to gemini-2.5-pro
                response = model.generate_content(prompt)
                return response.text
        except Exception as e:
            print(f"      - Error summarizing chunk: {e}")
            return ""

    def _analyze_content_with_llm(self, combined_content):
        if not combined_content or not combined_content.strip():
            return {"error": "No content to analyze."}

        # Define a safe token limit for the main prompt, leaving room for completion
        MAX_INPUT_TOKENS = 15000 # Increased token limit
        
        total_tokens = self._get_token_count(combined_content)
        print(f"Total tokens in combined content: {total_tokens}")

        if total_tokens > MAX_INPUT_TOKENS:
            print("  - Content exceeds token limit. Applying map-reduce summarization.")
            # Split the text into chunks based on tokens
            # A chunk size of 10000 tokens is a safe bet for most models
            CHUNK_SIZE = 10000 # Increased chunk size
            chunks = []
            
            # Simple text splitting logic, can be improved with more sophisticated chunking
            current_pos = 0
            while current_pos < len(combined_content):
                end_pos = current_pos + CHUNK_SIZE * 4 # Approximate chunking by character, then refine
                chunk_text = combined_content[current_pos:end_pos]
                
                # Refine chunk to not exceed token limit
                while self._get_token_count(chunk_text) > CHUNK_SIZE:
                    chunk_text = chunk_text[:-1000] # Trim down
                chunks.append(chunk_text)
                current_pos += len(chunk_text)

            print(f"  - Split content into {len(chunks)} chunks.")
            
            summaries = [self._summarize_chunk(chunk) for chunk in chunks]
            combined_content = "\n\n---" + " Combined Summaries of Document Chunks ---" + "\n".join(summaries)
            print(f"  - Total tokens in combined summaries: {self._get_token_count(combined_content)}")

        # Ensure even the summarized content doesn't exceed the limit
        if self._get_token_count(combined_content) > MAX_INPUT_TOKENS:
             combined_content = combined_content[:MAX_INPUT_TOKENS * 4] # Final safety trim
             while self._get_token_count(combined_content) > MAX_INPUT_TOKENS:
                 combined_content = combined_content[:-1000]
        

        
        prompt_v3 = f"""
        
        As an expert government contract analyst, your task is to meticulously review the following solicitation document(s) and extract key information into a structured JSON format. The document content might be a main solicitation description, content from downloaded attachments, or text scraped from linked web pages (including nested links). **When extracting product and delivery location details, prioritize specificity and accuracy from the original text, even if it comes from summarized sections.**
        

        
        Document Content:
        
        ---
        
        {combined_content}
        
        ---
        

        
        Based on the content, extract the following details into a valid JSON object:

        1.  **soliciting_entity**: The full name of the organization or entity issuing the solicitation (e.g., "Department of Defense", "NAVSUP WSS Mechanicsburg"). If not explicitly stated, try to infer from context. If not found, use an empty string.
        2.  **soliciting_contact_info**: A JSON object containing contact details for the soliciting entity.
            *   `email`: The primary contact email address.
            *   `phone`: The primary contact phone number.
            If not found, use empty strings.
        3.  **product_details**: A list of objects, where each object represents a primary product or service required. Be extremely precise and extract all available details. Each object should have the following keys:
            *   `line_item_number`: The solicitation line item number (e.g., CLIN 0001) if available.
            *   `name`: The name of the product or service.
            *   `description`: A detailed description of the product, including its purpose, function, and any other relevant descriptive information.
            *   `quantity`: The numerical quantity required.
            *   `unit`: The unit of measure (e.g., "EA" for Each).
            *   `part_number`: Any relevant part numbers, NSN, or catalog numbers.
            *   `specifications`: A detailed list of all technical specifications, standards (e.g., "MIL-PRF-27210"), materials, dimensions (size, weight), color, and any other physical or technical requirements. Capture this information as thoroughly as possible. If there are many specifications, present them as a list of strings.
            If a field is not found, use an empty string or an empty list for specifications. If no product details are found, return an empty list.
        4.  **delivery_location**: A JSON object with the location for delivery or performance. **It is crucial to extract this information diligently as it directly impacts vendor matching.** Be flexible in identifying the location. Look for terms like "Place of Performance", "Delivery Address", "Ship to", "Place of Replacement", "Shipment Area", "Location of Work", or any other address-like information that indicates where the product or service is needed.
            *   `street`: The street address.
            *   `city`: The city.
            *   `state`: The state.
            *   `zip_code`: The zip code.
            If a full address is not available, try to extract at least a city and state. If no location is found, return an empty object.
        5.  **summary**: A detailed summary (2-4 sentences) of the key requirements and scope.
        

        
Please provide your response in a clean JSON format.
        
        """

        try:
            analysis = {}
            if self.config.LLM_PROVIDER == "openai":
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo", # Changed model to gpt-3.5-turbo for broader access
                    messages=[{"role": "user", "content": prompt_v3}],
                    response_format={"type": "json_object"},
                    max_tokens=4000
                )
                analysis = json.loads(response.choices[0].message.content)
            else: # Default to gemini
                model = genai.GenerativeModel('gemini-2.5-pro', generation_config={"response_mime_type": "application/json"}) # Corrected model name to gemini-2.5-pro
                response = model.generate_content(prompt_v3)
                analysis = json.loads(response.text)

            return analysis

        except (json.JSONDecodeError, Exception) as e:
            print(f"Error during LLM analysis: {e}")
            try:
                # Attempt to extract JSON from a potentially malformed response string
                json_match = re.search(r'```json\n(.*)\n```', str(e), re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    return json.loads(json_str)
                else:
                    print("    - No JSON found in error message for recovery.")
            except Exception as inner_e:
                print(f"    - Inner exception during JSON recovery from error message: {inner_e}")
            return {"error": f"LLM analysis failed and could not recover. Details: {e}"}

    def create_summary_report(self, contract_id):
        solicitation_row = self.db_manager.get_solicitation_by_contract_id(contract_id)
        if not solicitation_row:
            return {"error": f"No solicitation found for contract ID: {contract_id}"}
        solicitation = dict(solicitation_row)

        attachments = self.db_manager.get_attachments_for_solicitation(contract_id)
        
        all_content_parts = [f"Solicitation Description:\n{solicitation.get('description', '')}"]

        if attachments:
            for i, attachment_row in enumerate(attachments):
                attachment = dict(attachment_row)
                print(f"Reading attachment: {attachment['file_name']}")
                content = self._read_file_content(attachment['file_path'])
                if content:
                    all_content_parts.append(f"\n\n---" + " Attachment " + str(i+1) + ": " + attachment['file_name'] + " ---\n" + content)
        
        combined_content = "\n".join(all_content_parts)

        structured_analysis = self._analyze_content_with_llm(combined_content)

        # Add solicitation-level info to the analysis
        structured_analysis['contract_id'] = contract_id
        structured_analysis['title'] = solicitation.get('title')
        structured_analysis['url'] = solicitation.get('url')

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
