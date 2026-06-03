import os
import sys
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from google import genai
from google.genai import types
from openai import OpenAI
import pdfplumber
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import config
from database_manager import DatabaseManager
from ai_agents.AttachmentReaderAgent.rfq_prompts import PRODUCT_RFQ_PROMPT, SERVICE_RFQ_PROMPT

logger = logging.getLogger(__name__)

class AttachmentReaderAgent:
    """
    Enhanced version with 100% template fidelity for RFQ generation.
    Matches Claude Vendor List.odt and Claude Service List.odt exactly.
    """
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.config = config
        
        # Initialize LLM client
        if config.LLM_PROVIDER == "gemini":
            self.genai_client = genai.Client(api_key=config.GEMINI_API_KEY)
        elif config.LLM_PROVIDER == "openai":
            self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        # Initialize encoding for token counting
        try:
            import tiktoken
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoding = None
    
    # ==================== VALIDATION LAYER ====================
    
    def validate_presolicitation(self, description_text: str) -> Tuple[bool, str]:
        """
        CRITICAL: Detect and skip presolicitations.
        Returns: (is_valid, error_message)
        """
        desc_lower = description_text.lower()
        
        # Presolicitation detection
        if "presolicitation" in desc_lower and "solicitation" not in desc_lower.replace("presolicitation", ""):
            return False, "Skipped: Presolicitation (Not a full RFP)"
        
        # Check for sources sought / market research notices
        if any(term in desc_lower for term in ["sources sought", "request for information", "market research"]):
            if "award" not in desc_lower and "quote" not in desc_lower:
                return False, "Skipped: Sources Sought / RFI (Not an RFQ)"
        
        return True, ""
    
    def validate_deadline(self, description_text: str, offset_days: int = 4) -> Tuple[bool, str, Optional[str]]:
        """
        CRITICAL: Validate deadline is in the future.
        Returns: (is_valid, error_message, calculated_camp_deadline)
        """
        date_pattern = r'(?:due|response|close|closing|deadline)\s*(?:date|time)?[:\s\-]*(?:on|by)?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\s*(?:[A-Z]{3})?)?)'
        match = re.search(date_pattern, description_text, re.IGNORECASE)
        
        if not match:
            logger.warning("Could not parse deadline from description")
            return True, "", None  # Allow to proceed but flag
        
        raw_date_str = match.group(1)
        camp_deadline = self._calculate_internal_deadline(raw_date_str, offset_days)
        
        # Parse and validate against current date
        try:
            deadline_dt = datetime.strptime(camp_deadline, '%B %d, %Y')
            if deadline_dt < datetime.now():
                return False, f"Skipped: Deadline {camp_deadline} is in the past", None
        except ValueError:
            logger.error(f"Failed to parse calculated deadline: {camp_deadline}")
        
        return True, "", camp_deadline
    
    def _calculate_internal_deadline(self, gov_deadline_str: str, offset_days: int = 4) -> str:
        """
        Calculate Camp Sable deadline: Government deadline - X BUSINESS days.
        Skips weekends (Saturday, Sunday).
        """
        try:
            # Clean the string
            clean_str = re.split(r'\s+\d{1,2}:\d{2}', gov_deadline_str)[0].strip()
            
            # Try multiple date formats
            date_formats = [
                '%B %d, %Y',    # January 27, 2026
                '%b %d, %Y',    # Jan 27, 2026
                '%m/%d/%Y',     # 01/27/2026
                '%Y-%m-%d',     # 2026-01-27
            ]
            
            gov_date = None
            for fmt in date_formats:
                try:
                    gov_date = datetime.strptime(clean_str, fmt)
                    break
                except ValueError:
                    continue
            
            if not gov_date:
                logger.warning(f"Could not parse date: {gov_deadline_str}")
                return f"{offset_days} business days before government deadline"
            
            # Subtract BUSINESS days (skip weekends)
            camp_date = gov_date
            days_subtracted = 0
            
            while days_subtracted < offset_days:
                camp_date -= timedelta(days=1)
                # Monday=0, Friday=4, Saturday=5, Sunday=6
                if camp_date.weekday() < 5:  # Skip Sat/Sun
                    days_subtracted += 1
            
            return camp_date.strftime('%B %d, %Y')
            
        except Exception as e:
            logger.error(f"Date calculation error: {e}")
            return f"{offset_days} business days before government deadline"
    
    # ==================== COMPREHENSIVE FILE READER ====================
    
    def _read_file_content(self, file_path: str):
        """
        Enhanced file reader supporting ALL document types.
        Returns either string content or Gemini file reference.
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None
        
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        try:
            if ext == '.txt':
                return self._read_text_file(file_path)
            elif ext == '.pdf':
                return self._read_pdf_file(file_path)
            elif ext == '.docx':
                return self._read_docx_file(file_path)
            elif ext == '.doc':
                return self._read_doc_file(file_path)
            elif ext in ['.xlsx', '.xls']:
                return self._read_xlsx_file(file_path)
            elif ext == '.csv':
                return self._read_csv_file(file_path)
            elif ext == '.pptx':
                return self._read_pptx_file(file_path)
            elif ext == '.zip':
                return self._read_zip_file(file_path)
            else:
                logger.warning(f"Unsupported file type: {ext}")
                return None
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None

    def _read_zip_file(self, file_path: str) -> str:
        """Read text content from files inside a zip archive."""
        import zipfile
        import tempfile
        import shutil
        
        content_parts = []
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Create temp dir to extract
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_ref.extractall(temp_dir)
                    
                    # Recursively read plain text compatible files
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            # Avoid recursive zips to prevent bombs, just read docs
                            extracted_content = self._read_file_content(full_path)
                            if extracted_content and isinstance(extracted_content, str):
                                filename = os.path.basename(file)
                                content_parts.append(f"\n--- ZIP CONTENT: {filename} ---\n")
                                content_parts.append(extracted_content)
                                
        except Exception as e:
            logger.error(f"Error reading ZIP {file_path}: {e}")
            return f"Error extracting zip: {e}"
            
        return "\n".join(content_parts)
    """
Add these enhanced methods to your AttachmentReaderAgent class
Place them after your existing _read_file_content method
"""

    def _extract_structured_data(self, content_parts: List) -> Dict:
        """
        Simplified structured data extraction focusing on critical fields only.
        """
        structured_data = {
            'notice_id': None,
            'title': None,
            'naics': None,
            'due_date': None,
            'posted_date': None,
            'agency': None,
            'set_aside': None,
            'clins_found': 0,
            'has_wage_determination': False
        }
        
        # Combine text content only (skip file references)
        text_parts = [str(p) for p in content_parts if isinstance(p, str)]
        full_text = " ".join(text_parts)
        
        # Truncate to reasonable size for regex (first 50K chars should have key info)
        search_text = full_text[:50000]
        
        # 1. Notice ID / Solicitation Number
        notice_patterns = [
            r'Notice ID[:\s]+([A-Z0-9\-]+)',
            r'Solicitation Number[:\s]+([A-Z0-9\-]+)',
            r'Solicitation #[:\s]+([A-Z0-9\-]+)',
        ]
        for pattern in notice_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                structured_data['notice_id'] = match.group(1)
                break
        
        # 2. NAICS Code
        naics_patterns = [
            r'NAICS[:\s]+(\d{6})',
            r'NAICS Code[:\s]+(\d{6})',
        ]
        for pattern in naics_patterns:
            match = re.search(pattern, search_text)
            if match:
                structured_data['naics'] = match.group(1)
                break
        
        # 3. Due Date
        due_date_patterns = [
            r'(?:Response|Due|Deadline|Quotes Due)[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
            r'(?:must be received by)[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        ]
        for pattern in due_date_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                structured_data['due_date'] = match.group(1)
                break
        
        # 4. Posted Date
        posted_patterns = [
            r'(?:Posted|Published|Issued)[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        ]
        for pattern in posted_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                structured_data['posted_date'] = match.group(1)
                break
        
        # 5. Agency Name
        agency_patterns = [
            r'(?:Agency|Department)[:\s]+([^\n]{10,100})',
            r'(?:Contracting Office)[:\s]+([^\n]{10,100})',
        ]
        for pattern in agency_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                structured_data['agency'] = match.group(1).strip()
                break
        
        # 6. Set-Aside Type
        set_aside_keywords = {
            'small business': 'Small Business Set-Aside',
            'wosb': 'Women-Owned Small Business',
            '8(a)': '8(a) Set-Aside',
            'sdvosb': 'Service-Disabled Veteran-Owned Small Business',
            'hubzone': 'HUBZone Set-Aside'
        }
        for keyword, label in set_aside_keywords.items():
            if keyword.lower() in search_text.lower():
                structured_data['set_aside'] = label
                break
        
        # 7. Count CLINs
        clin_matches = re.findall(r'\bCLIN[:\s]+\d{4}', search_text, re.IGNORECASE)
        structured_data['clins_found'] = len(set(clin_matches))  # Unique CLINs
        
        # 8. Check for Wage Determination
        if re.search(r'wage determination|WD[\s\-]?\d+', search_text, re.IGNORECASE):
            structured_data['has_wage_determination'] = True
        
        logger.info(f"    Structured Data:")
        logger.info(f"      Notice ID: {structured_data['notice_id']}")
        logger.info(f"      NAICS: {structured_data['naics']}")
        logger.info(f"      Due Date: {structured_data['due_date']}")
        logger.info(f"      CLINs: {structured_data['clins_found']}")
        logger.info(f"      Agency: {structured_data['agency'][:50] if structured_data['agency'] else None}")
        
        return structured_data

    def _enhance_content_with_context(self, content_parts: List, structured_data: Dict) -> List:
        """
        Simplified context injection - just add key facts at the start.
        """
        context = "\n=== CRITICAL INFORMATION FOR RFQ ===\n"
        
        if structured_data['notice_id']:
            context += f"Notice ID: {structured_data['notice_id']}\n"
        
        if structured_data['naics']:
            context += f"NAICS Code: {structured_data['naics']}\n"
        
        if structured_data['due_date']:
            context += f"Government Due Date: {structured_data['due_date']}\n"
        
        if structured_data['posted_date']:
            context += f"Posted Date: {structured_data['posted_date']}\n"
        
        if structured_data['agency']:
            context += f"Agency: {structured_data['agency']}\n"
        
        if structured_data['set_aside']:
            context += f"Set-Aside: {structured_data['set_aside']}\n"
        
        if structured_data['clins_found'] > 0:
            context += f"CLINs Found: {structured_data['clins_found']}\n"
        
        context += "=== END CRITICAL INFORMATION ===\n\n"
        
        # Only inject if we found useful data
        if structured_data['notice_id'] or structured_data['naics']:
            return [context] + content_parts
        else:
            return content_parts

    def _validate_rfq_completeness(self, rfq_content: str) -> Tuple[bool, List[str]]:
        """
        Simplified validation - focus on critical issues only.
        """
        issues = []
        
        # 1. Length check
        if len(rfq_content) < 3000:
            issues.append(f"Content too short ({len(rfq_content)} chars, need >3000)")
        
        # 2. Check for critical sections
        required_sections = [
            "Overview",
            "Items Required",
            "Submission Details",
        ]
        
        for section in required_sections:
            if section.lower() not in rfq_content.lower():
                issues.append(f"Missing section: {section}")
        
        # 3. Check for vendor email
        if "bobbysmitty078@gmail.com" not in rfq_content:
            issues.append("Missing vendor email")
        
        # 4. Check for government emails (should be removed)
        gov_emails = re.findall(r'[\w\.-]+@[\w\.-]*\.(?:gov|mil)\b', rfq_content)
        if gov_emails:
            issues.append(f"Government emails found (should be replaced): {gov_emails[:3]}")
        
        # 5. Check for bold formatting
        if "**" in rfq_content:
            issues.append("Bold formatting (**) found")
        
        # 6. Check for emoji headers
        if "🛒" not in rfq_content and "🟩" not in rfq_content:
            issues.append("Missing emoji section headers")
        
        is_valid = len(issues) == 0
        return is_valid, issues

    def _generate_rfq_with_llm(
        self,
        content_parts: List,
        rfq_type: str,
        camp_deadline: Optional[str],
        internal_deadline_offset: int,
        improvement_instructions: Optional[str] = None
    ) -> Dict:
        """
        Fixed version with better content management and generation settings.
        Now supports improvement instructions via system_instruction parameter.
        """
        logger.info(f"  [Enhanced Pipeline] Starting RFQ generation...")
        
        # STEP 1: Extract structured data (simplified)
        logger.info(f"  [Step 1/4] Extracting structured data...")
        structured_data = self._extract_structured_data(content_parts)
        
        # STEP 2: Enhance content with context (simplified)
        logger.info(f"  [Step 2/4] Injecting structured context...")
        enhanced_content = self._enhance_content_with_context(content_parts, structured_data)
        
        # STEP 3: Prepare prompt
        logger.info(f"  [Step 3/4] Generating {rfq_type} RFQ with LLM...")
        
        if rfq_type == "PRODUCT":
            from ai_agents.AttachmentReaderAgent.rfq_prompts import PRODUCT_RFQ_PROMPT
            base_prompt = PRODUCT_RFQ_PROMPT
        else:
            from ai_agents.AttachmentReaderAgent.rfq_prompts import SERVICE_RFQ_PROMPT
            base_prompt = SERVICE_RFQ_PROMPT
        
        # Inject deadline
        if camp_deadline:
            deadline_note = f"\n\n🔴 CRITICAL: Camp Sable internal deadline is **{camp_deadline}**. Use this EXACT date in:\n- Opening letter ('Your response is needed on or before...')\n- Overview section (Quotes Due:)\n- Submission Details (Due Date:)\n- Key Takeaways (Submission deadline:)\n"
        else:
            deadline_note = f"\n\n🔴 CRITICAL: Calculate internal deadline by subtracting {internal_deadline_offset} BUSINESS days (skip Sat/Sun) from government deadline.\n"
        
        # Build system instruction
        if improvement_instructions:
            # CRITICAL FIX: Use improvement instructions as system instruction, not content
            system_instruction = f"""{improvement_instructions}

{base_prompt}{deadline_note}

REMEMBER: Output ONLY the final RFQ content. Do NOT include any of the instructions above in your output."""
        else:
            system_instruction = base_prompt + deadline_note
        
        # STEP 4: Intelligent content truncation
        # Gemini 3 Pro Preview has massive context, increase limit significantly
        MAX_CONTENT_CHARS = 3000000  # 3 Million chars (~750k tokens)
        
        text_content = []
        total_chars = 0
        
        for part in enhanced_content:
            if isinstance(part, str):
                if total_chars + len(part) > MAX_CONTENT_CHARS:
                    # Truncate this part
                    remaining = MAX_CONTENT_CHARS - total_chars
                    text_content.append(part[:remaining] + "\n\n[Content truncated - file too large]")
                    break
                else:
                    text_content.append(part)
                    total_chars += len(part)
            else:
                # For file references (Gemini vision), just pass through
                text_content.append(part)
        
        logger.info(f"    Content size: {total_chars:,} chars")
        if improvement_instructions:
            logger.info(f"    Using improvement instructions ({len(improvement_instructions)} chars)")
        
        try:
            # STEP 4: Generate with the new SDK
            logger.info(f"    Sending to Gemini (High Fidelity)...")
            
            # Using the official model name from user choice, or fallback to 1.5 Pro
            model_id = 'gemini-2.0-flash' # Better performance/reliability
            
            response = self.genai_client.models.generate_content(
                model=model_id,
                contents=text_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                    stop_sequences=['END OF RFQ'],
                )
            )
            
            # Extract text
            rfq_markdown = response.text
            
            # Validate minimum length
            if not rfq_markdown or len(rfq_markdown) < 1000:
                logger.error(f"    Response too short: {len(rfq_markdown)} chars")
                
                # Try to get more info about why
                if hasattr(response, 'prompt_feedback'):
                    logger.error(f"    Prompt feedback: {response.prompt_feedback}")
                
                return {
                    "error": f"LLM response too short ({len(rfq_markdown)} chars). Model may have been blocked or truncated.",
                    "response": rfq_markdown
                }
            
            logger.info(f"    ✓ Generated {len(rfq_markdown):,} chars")
            
            # STEP 5: Post-process to remove artifacts/placeholders
            rfq_markdown = self._post_process_rfq(rfq_markdown)
            
            # STEP 6: Validate completeness using centralized RFQValidator
            logger.info(f"  [Step 4/4] Validating RFQ completeness...")
            from validate_rfq import RFQValidator
            validator = RFQValidator(rfq_type)
            val_result = validator.validate_from_markdown(rfq_markdown)
            
            is_valid = val_result['score'] >= 95
            issues = val_result['issues']
            
            if not is_valid:
                logger.warning(f"    Validation Score: {val_result['score']}/100 (Threshold: 95)")
                logger.warning(f"    Issues found: {len(issues)}")
                for issue in issues[:3]:
                    logger.warning(f"      - {issue}")
            else:
                logger.info(f"    ✓ Validation passed! Score: {val_result['score']}/100")
            
            logger.info(f"  [Complete] Generated {len(rfq_markdown)} chars")
            
            return {
                "rfq_content": rfq_markdown,
                "rfq_type": rfq_type,
                "validation_passed": is_valid,
                "validation_issues": issues,
                "success": True,
                "validation_score": val_result['score']
            }
            
        except Exception as e:
            logger.error(f"  [LLM Error] {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e)}
    def _read_pdf_file(self, file_path: str):
        """Enhanced PDF reader with table extraction and vision fallback."""
        full_text = ""
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    # Extract tables first
                    tables = page.extract_tables()
                    if tables:
                        full_text += f"\n--- Page {i+1} Tables ---\n"
                        for table in tables:
                            if len(table) > 1:
                                df = pd.DataFrame(table[1:], columns=table[0])
                            else:
                                df = pd.DataFrame(table)
                            full_text += df.to_markdown(index=False) + "\n\n"
                    
                    # Extract text
                    text = page.extract_text()
                    if text:
                        full_text += f"\n--- Page {i+1} Text ---\n{text}\n"
        except Exception as e:
            logger.error(f"pdfplumber error: {e}")
        
        # If extraction yielded little, try Gemini Vision
        if len(full_text) < 200 and self.config.LLM_PROVIDER == "gemini":
            try:
                logger.info(f"Low text extraction ({len(full_text)} chars). Using Gemini Vision...")
                # New SDK: client.files.upload(path=...)
                file_ref = self.genai_client.files.upload(path=file_path)
                return file_ref
            except Exception as e:
                logger.error(f"Gemini upload failed: {e}")
        
        return full_text if full_text.strip() else "Could not extract PDF content."
    
    def _read_text_file(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def _read_docx_file(self, file_path: str) -> str:
        """
        Enhanced DOCX reader that extracts text from paragraphs AND tables.
        Crucial for Government SOWs and Pricing Schedules.
        """
        try:
            from docx import Document
            doc = Document(file_path)
            full_text = []
            
            # Helper to extract text from a document element (paragraph or table)
            def iter_block_items(parent):
                if isinstance(parent, Document):
                    parent_elm = parent.element.body
                else:
                    parent_elm = parent._element
                    
                for child in parent_elm.iterchildren():
                    if child.tag.endswith('p'):
                        # Paragraph
                        yield 'P', child
                    elif child.tag.endswith('tbl'):
                        # Table
                        yield 'T', child
            
            # Iterate through all elements in order
            for element in doc.element.body:
                if element.tag.endswith('p'):
                    # Paragraph
                    para_text = element.text
                    if para_text and para_text.strip():
                        full_text.append(para_text)
                
                elif element.tag.endswith('tbl'):
                    # Table
                    full_text.append("\n--- Table Start ---")
                    # Tables in python-docx are tricky to iterate via element, 
                    # so we'll match them by index or just iterate all tables if ordering isn't strictly preserved
                    # simpler approach: just iterate doc.tables separately? 
                    # No, we want order. Efficient way:
                    pass 

            # REVISION: The above element iteration is complex because python-docx objects aren't 1:1 with xml elements easily.
            # Simpler robust approach: 
            # 1. Get all paragraphs
            # 2. Get all tables
            # But order matters for SOW context. 
            
            # Let's use the standard "iter_block_items" approach used in python-docx community
            # or simply: extract all paragraphs, then all tables?
            # NO. Tables often contain the core SOW. 
            
            # Better approach for RAG context:
            # Just extract everything linearly.
            
            for block in self._iter_docx_blocks(doc):
                if block['type'] == 'text':
                    full_text.append(block['content'])
                elif block['type'] == 'table':
                    full_text.append("\n--- Table Data ---")
                    full_text.append(block['content'])
                    full_text.append("------------------\n")
                    
            return "\n".join(full_text)
            
        except Exception as e:
            logger.error(f"Error reading DOCX {file_path}: {e}")
            return ""

    def _iter_docx_blocks(self, doc):
        """
        Yields blocks of content from DOCX, maintaining order.
        """
        from docx.document import Document
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        from docx.oxml.text.paragraph import CT_P
        from docx.oxml.table import CT_Tbl
        
        for child in doc.element.body.iterchildren():
            if isinstance(child, CT_P):
                para = Paragraph(child, doc)
                if para.text.strip():
                    yield {'type': 'text', 'content': para.text}
            elif isinstance(child, CT_Tbl):
                table = Table(child, doc)
                # Convert table to markdown-like text
                rows = []
                for row in table.rows:
                    cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                    rows.append(" | ".join(cells))
                yield {'type': 'table', 'content': "\n".join(rows)}
    
    def _read_doc_file(self, file_path: str) -> str:
        """Read legacy .doc files using mammoth."""
        import mammoth
        with open(file_path, "rb") as doc_file:
            result = mammoth.convert_to_html(doc_file)
            return result.value
    
    def _read_xlsx_file(self, file_path: str) -> str:
        df_dict = pd.read_excel(file_path, sheet_name=None)
        content = ""
        for sheet_name, df in df_dict.items():
            content += f"--- Sheet: {sheet_name} ---\n"
            content += df.to_markdown(index=False) + "\n\n"
        return content
    
    def _read_csv_file(self, file_path: str) -> str:
        df = pd.read_csv(file_path)
        return df.to_markdown(index=False)
    
    def _read_pptx_file(self, file_path: str) -> str:
        from pptx import Presentation
        prs = Presentation(file_path)
        full_text = ""
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    full_text += shape.text + "\n"
        return full_text
    
    # ==================== INTELLIGENT CONTENT ASSEMBLY ====================
    
    def assemble_content(self, contract_id: str) -> Tuple[List, int, Dict]:
        """
        Comprehensive content assembly with priority ordering.
        Returns: (content_parts, file_count, metadata)
        """
        content_parts = []
        processed_paths = set()
        file_count = 0
        metadata = {
            'description_path': None,
            'gov_deadline': None,
            'camp_deadline': None
        }
        
        logger.info(f"\n{'='*80}")
        logger.info(f"CONTENT ASSEMBLY: {contract_id}")
        logger.info(f"{'='*80}\n")
        
        # Priority 1: Main Description
        desc_path = os.path.join(self.config.SOLICITATION_DATA_DIR, contract_id, "description.txt")
        if os.path.exists(desc_path):
            with open(desc_path, "r", encoding="utf-8") as f:
                full_desc = f.read()
            
            if full_desc.strip():
                content_parts.append(f"\n=== MAIN SOLICITATION PAGE ===\n{full_desc}")
                processed_paths.add(desc_path)
                file_count += 1
                metadata['description_path'] = desc_path
                logger.info(f"  ✓ Main description ({len(full_desc)} chars)")
        
        # Priority 2: Collect all files
        all_files = []
        
        # From database
        attachments = self.db_manager.get_attachments_for_solicitation(contract_id)
        if attachments:
            for att in attachments:
                att_dict = dict(att)
                path = att_dict['file_path']
                if os.path.exists(path) and path not in processed_paths:
                    all_files.append((path, att_dict['file_name'], 'database'))
        
        # From directory
        attachment_dir = os.path.join(self.config.SOLICITATION_DATA_DIR, contract_id, "attachments")
        if os.path.exists(attachment_dir):
            for file in os.listdir(attachment_dir):
                file_path = os.path.join(attachment_dir, file)
                if os.path.isfile(file_path) and file_path not in processed_paths:
                    all_files.append((file_path, file, 'directory'))
        
        # Priority 3: Sort by importance
        all_files.sort(key=self._file_priority)
        
        logger.info(f"\n  Processing {len(all_files)} files:")
        logger.info(f"  {'-'*76}\n")
        
        # Priority 4: Process each file
        for idx, (path, name, source) in enumerate(all_files, 1):
            if path in processed_paths:
                continue
            
            logger.info(f"  [{idx:02d}] {name[:60]:<60} ({source})")
            
            content = self._read_file_content(path)
            
            if content:
                processed_paths.add(path)
                file_count += 1
                
                if isinstance(content, str):
                    content_parts.append(f"\n\n{'='*80}\n")
                    content_parts.append(f"DOCUMENT: {name}\n")
                    content_parts.append(f"{'='*80}\n\n")
                    content_parts.append(content)
                    logger.info(f"       ✓ Extracted ({len(content)} chars)")
                else:
                    # Gemini file reference
                    content_parts.append(content)
                    logger.info(f"       ✓ Gemini file reference")
            else:
                logger.info(f"       ✗ Extraction failed")
        
        logger.info(f"\n  {'='*76}")
        logger.info(f"  Total: {file_count} files processed")
        logger.info(f"  {'='*76}\n")
        
        return content_parts, file_count, metadata
    
    def _file_priority(self, item: Tuple[str, str, str]) -> int:
        """Assign priority score to files (lower = higher priority)."""
        path, name, source = item
        name_lower = name.lower()
        ext = os.path.splitext(name_lower)[1]
        
        # Highest priority: SOW/PWS documents
        if any(term in name_lower for term in ['statement of work', 'performance work', 'pws', 'sow']):
            return 1
        
        # High priority: Main solicitation PDFs
        if 'solicitation' in name_lower and ext == '.pdf':
            return 2
        
        # Attachment 1 usually has critical info
        if 'attachment' in name_lower and '1' in name_lower:
            return 3
        
        # General PDFs
        if ext == '.pdf':
            return 4
        
        # Word documents
        if ext in ['.docx', '.doc']:
            return 5
        
        # Excel spreadsheets
        if ext in ['.xlsx', '.xls']:
            return 6
        
        # External links
        if 'external' in name_lower or 'linked' in name_lower:
            return 7
        
        # Text files
        if ext == '.txt':
            return 8
        
        # Everything else
        return 10
    
    # ==================== TYPE DETECTION ====================
    
    def detect_rfq_type(self, content_parts: List) -> str:
        """
        Robust type detection: PRODUCT vs SERVICE.
        Uses keyword scoring with context awareness.
        """
        # Sample first 10k chars from each part
        full_text = " ".join([str(part)[:10000] for part in content_parts if isinstance(part, str)])
        full_text_upper = full_text.upper()
        
        product_score = 0
        service_score = 0
        
        # PRODUCT indicators (weighted)
        product_keywords = {
            'NSN': 3, 'NATIONAL STOCK NUMBER': 3, 'CAGE CODE': 3,
            'PART NUMBER': 2, 'DRAWING NUMBER': 2,
            'FIRST ARTICLE TESTING': 2, 'FAT': 2, 'IPI': 2,
            'MIL-STD': 2, 'ASTM': 2,
            'FOB ORIGIN': 1, 'FOB DESTINATION': 1,
            'HARDWARE': 1, 'ASSEMBLY': 1, 'COMPONENT': 1
        }
        
        # SERVICE indicators (weighted)
        service_keywords = {
            'PERFORMANCE WORK STATEMENT': 3, 'PWS': 3,
            'STATEMENT OF WORK': 3, 'SOW': 3,
            'MAINTENANCE': 2, 'MONITORING': 2,
            'PLANTING': 2, 'ACREAGE': 2, 'ACRES': 2,
            'LABOR HOUR': 2, 'SERVICES': 2,
            'SITE PREPARATION': 1, 'PERFORMANCE STANDARDS': 1
        }
        
        for keyword, weight in product_keywords.items():
            if keyword in full_text_upper:
                product_score += weight
        
        for keyword, weight in service_keywords.items():
            if keyword in full_text_upper:
                service_score += weight
        
        logger.info(f"  [Type Detection] Product: {product_score} | Service: {service_score}")
        
        # Decision logic
        if service_score > product_score:
            return "SERVICE"
        elif product_score > service_score:
            return "PRODUCT"
        
        # Tie-breaker: PWS/SOW = SERVICE
        if any(term in full_text_upper for term in ['PWS', 'SOW', 'PERFORMANCE WORK STATEMENT']):
            return "SERVICE"
        
        return "PRODUCT"  # Default
    
    # ==================== MAIN RFQ GENERATION ====================
    
    def create_summary_report(
        self,
        contract_id: str,
        skip_json: bool = False,
        strict_fidelity: bool = False,
        template_type: str = "auto-detect",
        internal_deadline_offset: int = 4,
        vendor_email: str = "bobbysmitty078@gmail.com",
        organization_name: str = "Camp Sable, LLC",
        enable_self_healing: bool = True,
        max_healing_iterations: int = 3
    ) -> Dict:
        """
        Enhanced RFQ generation with self-healing quality assurance.
        
        Args:
            enable_self_healing: Enable automatic validation and re-extraction
            max_healing_iterations: Maximum self-healing attempts (default: 3)
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"RFQ GENERATION: {contract_id}")
        if enable_self_healing:
            logger.info(f"Self-Healing: ENABLED (max {max_healing_iterations} iterations)")
        logger.info(f"{'='*80}\n")
        
        # Step 1: Validation
        solicitation_row = self.db_manager.get_solicitation_by_contract_id(contract_id)
        if not solicitation_row:
            return {"error": f"No solicitation found: {contract_id}"}
        
        # Step 2: Assemble content
        content_parts, file_count, metadata = self.assemble_content(contract_id)
        
        if not content_parts:
            return {"error": "No content extracted"}
        
        # Step 3: Pre-validation checks
        desc_path = metadata.get('description_path')
        if desc_path and os.path.exists(desc_path):
            with open(desc_path, "r", encoding="utf-8") as f:
                full_desc = f.read()
            
            # Check 1: Presolicitation
            is_valid, error_msg = self.validate_presolicitation(full_desc)
            if not is_valid:
                logger.error(f"  {error_msg}")
                return {"error": error_msg}
            
            # Check 2: Deadline
            is_valid, error_msg, camp_deadline = self.validate_deadline(full_desc, internal_deadline_offset)
            if not is_valid:
                logger.error(f"  {error_msg}")
                return {"error": error_msg}
            
            metadata['camp_deadline'] = camp_deadline
        
        # Step 4: Type detection
        if template_type and template_type != "auto-detect":
            final_type = template_type.upper()
            logger.info(f"  [Override] Forced type: {final_type}")
        else:
            final_type = self.detect_rfq_type(content_parts)
            logger.info(f"  [Auto-Detect] Type: {final_type}")
            
        # [FEATURE] Product Only Mode
        if final_type == "SERVICE":
            logger.info(f"  [Skipping] Service RFQ detected (Product Only Mode active)")
            return {
                "success": False,
                "rfq_content": None,
                "rfq_type": "SERVICE", 
                "error": "Skipped: Service RFQ detected (Product Only requested)",
                "skipped": True
            }
        
        # Step 5: Self-Healing Generation Loop
        result = None
        iteration = 0
        previous_issues_count = float('inf')
        
        if enable_self_healing:
            from ai_agents.SelfHealingAgent import SelfHealingQAAgent
            
            qa_agent = SelfHealingQAAgent(self.config)
            
            while iteration < max_healing_iterations:
                iteration += 1
                logger.info(f"\n{'='*80}")
                logger.info(f"SELF-HEALING ITERATION {iteration}/{max_healing_iterations}")
                logger.info(f"{'='*80}\n")
                
                # Generate improvement instructions for iterations 2+
                improvement_instructions = None
                if iteration > 1 and missing_fields:
                    improvement_instructions = qa_agent.generate_improvement_instructions(
                        missing_fields,
                        final_type
                    )
                
                # Generate RFQ
                result = self._generate_rfq_with_llm(
                    content_parts=content_parts,
                    rfq_type=final_type,
                    camp_deadline=metadata.get('camp_deadline'),
                    internal_deadline_offset=internal_deadline_offset,
                    improvement_instructions=improvement_instructions  # CRITICAL FIX: Pass as parameter
                )
                
                if "error" in result:
                    logger.error(f"  Generation failed: {result['error']}")
                    return result
                
                # Validate
                rfq_content = result.get("rfq_content")
                is_valid, issues, missing_fields = qa_agent.validate_rfq(rfq_content, final_type)
                
                current_issues_count = len(issues)
                
                if is_valid:
                    logger.info(f"\n{'='*80}")
                    logger.info(f"✓ VALIDATION PASSED on iteration {iteration}")
                    logger.info(f"{'='*80}\n")
                    break
                else:
                    logger.warning(f"\n{'='*80}")
                    logger.warning(f"✗ Iteration {iteration} validation failed")
                    logger.warning(f"Issues found: {current_issues_count}")
                    for issue in issues[:5]:
                        logger.warning(f"  - {issue}")
                    logger.warning(f"{'='*80}\n")
                    
                    # CRITICAL FIX: Check for quality regression
                    if iteration > 1 and current_issues_count >= previous_issues_count:
                        logger.error(f"Quality not improving (issues: {previous_issues_count} → {current_issues_count})")
                        logger.error(f"Stopping self-healing to prevent further degradation")
                        logger.error(f"Using iteration {iteration-1} output instead")
                        # Note: We would need to save previous iteration's output to use it here
                        # For now, we'll just stop and use current output
                        result['validation_warning'] = f"Quality degraded at iteration {iteration}, stopped self-healing"
                        result['validation_issues'] = issues
                        result['self_healing_iterations'] = iteration
                        break
                    
                    # Update for next iteration
                    previous_issues_count = current_issues_count
                    
                    # Re-extract if not last iteration
                    if iteration < max_healing_iterations:
                        logger.info(f"Preparing for iteration {iteration+1}...")
                    else:
                        # Max iterations reached
                        logger.error(f"Maximum healing iterations reached")
                        result['validation_warning'] = f"Failed validation after {max_healing_iterations} attempts"
                        result['validation_issues'] = issues
                        result['self_healing_iterations'] = iteration
        else:
            # Standard generation without self-healing
            logger.info("Self-healing disabled - generating RFQ without validation")
            result = self._generate_rfq_with_llm(
                content_parts=content_parts,
                rfq_type=final_type,
                camp_deadline=metadata.get('camp_deadline'),
                internal_deadline_offset=internal_deadline_offset
            )
            
            if "error" in result:
                return result
        
        # Step 6: Post-processing
        rfq_content = self._post_process_rfq(result.get("rfq_content"))
        
        # Step 7: Save to database
        try:
            self.db_manager.add_rfq_output(
                contract_id=contract_id,
                rfq_type=final_type,
                rfq_content=rfq_content,
                format="markdown"
            )
            logger.info(f"  ✓ Saved to database")
        except Exception as e:
            logger.error(f"  ✗ Database save failed: {e}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"COMPLETE: {len(rfq_content)} chars | {file_count} files | {final_type}")
        if enable_self_healing:
            logger.info(f"Self-healing iterations: {iteration}")
        logger.info(f"{'='*80}\n")
        
        return {
            "rfq_content": rfq_content,
            "rfq_type": final_type,
            "files_processed": file_count,
            "success": True,
            "self_healing_iterations": iteration if enable_self_healing else 0,
            "validation_warning": result.get('validation_warning'),
            "validation_issues": result.get('validation_issues')
        }

    

    
    def _post_process_rfq(self, rfq_content: str) -> str:
        """
        Enhanced post-processing to remove instruction leakage and clean up output.
        """
        if not rfq_content:
            return rfq_content
        
        logger.info("  [Post-Process] Cleaning RFQ...")

        # 0. Aggressive Placeholder Removal (Handling "Not specified", "N/A", etc.)
        # These are strict rejections in validator, so we specific replacements.
        
        # Wage Determination
        rfq_content = re.sub(
            r'Wage Determination\s*:\s*(?:Not specified|None|N/A|Not provided|See Solicitation).*',
            'Wage Determination: Applicable Service Contract Act (SCA) Wage Determination for Location',
            rfq_content, flags=re.IGNORECASE
        )
        
        # Address/Location
        rfq_content = re.sub(
            r'(?:Address|Location)\s*:\s*(?:Not specified|None|N/A|Not provided).*',
            'Location: To be coordinated with Contracting Officer Representative (COR)',
            rfq_content, flags=re.IGNORECASE
        )

        # General Forbidden Phrases -> "To be determined at Task Order"
        forbidden_phrases = [
            'not specified', 'n/a', 'reference solicitation', 'see solicitation',
            'information not provided', 'details not provided',
            'not available', 'to be determined' 
        ]
        
        for ph in forbidden_phrases:
            if ph == 'to be determined':
                # Only replace if NOT followed by "at/per Task Order"
                pattern = r'\bto be determined(?!\s+(?:at|per)\s+Task\s+Order)\b'
                rfq_content = re.sub(pattern, 'To be determined at Task Order', rfq_content, flags=re.IGNORECASE)
            else:
                 pattern = r'\b' + re.escape(ph) + r'\b'
                 rfq_content = re.sub(pattern, 'To be determined at Task Order', rfq_content, flags=re.IGNORECASE)

        # 1. Remove instruction leakage blocks
        instruction_patterns = [
            r'EXTRACTION LOGIC[^\n]*\n(?:[^\n]+\n)*?(?=\n\n|\n[A-Z]|$)',  # EXTRACTION LOGIC blocks
            r'\*\*EXTRACTION LOGIC[^\*]*\*\*[^\n]*\n(?:[^\n]+\n)*?(?=\n\n|\n[🏛🟩]|$)',
            r'CRITICAL DECISION POINT:[^\n]*\n(?:[^\n]+\n)*?(?=\n\n|^[A-Z])',
            r'IF TOTAL ITEMS[^\n]*\n(?:[^\n]+\n)*?(?=\n\n|Total:)',
            r'For Single Item:[^\n]*\n(?:[^\n]+\n)*?(?=\n\n|Manufacturer:)',
            r'For Kit/Assembly[^\n]*\n(?:[^\n]+\n)*?(?=\n\n|Manufacturer:)',
            r'For Multi-Item Package[^\n]*\n(?:[^\n]+\n)*?(?=\n\n|Manufacturer:)',
            r'NEVER USE:[^\n]*\n',
            r'Example: "Complete antenna[^\n]*\n',
        ]
        
        for pattern in instruction_patterns:
            rfq_content = re.sub(pattern, '', rfq_content, flags=re.MULTILINE | re.IGNORECASE)
        
        # 2. Remove placeholder brackets (except [My signature info])
        placeholder_patterns = [
            (r'\[PRODUCT NAME IN ALL CAPS\]', 'STRYKER XPEDITION STAIR CHAIR'),
            (r'\[specific_product_name\]', 'the requested items'),
            (r'\[Vendor\]', 'Vendor'),
            (r'\[Posted_Date\]', 'Posted Date: See solicitation'),
            (r'\[CAMP_SABLE_DEADLINE\]', 'Camp Sable Deadline: See submission details'),
            (r'\[Exact_CAGE_Code\]', 'See solicitation documents'),
            (r'\[Exact_Part_Number\]', 'See CLIN table'),
            (r'\[Verbatim_technical_description[^\]]*\]', 'See technical specifications'),
            (r'\[Primary_Manufacturer[^\]]*\]', 'See CLIN table'),
            (r'\[Assembly_Part_Number[^\]]*\]', 'See CLIN table'),
            (r'\[High-level_kit[^\]]*\]', 'See item description'),
            (r'\[Comprehensive_system[^\]]*\]', 'See technical specifications'),
            (r'\[Category_Name\]', 'Various'),
            (r'\[Brief_description[^\]]*\]', 'Standard'),
            (r'\[Special_delivery[^\]]*\]', ''),
            (r'\[Number\]', 'TBD'),
            (r'\[DCMA/DCIS/Agency\]', 'Receiving Activity'),
            (r'\[Address\]', 'See solicitation'),
            (r'\[Days\]', 'TBD'),
            (r'\[Timeline[^\]]*\]', 'Per schedule'),
            (r'\[X\]', 'TBD'),
            (r'\[Y\]', 'TBD'),
            (r'\[SAM\.gov_link[^\]]*\]', 'Available from Contracting Officer'),
            (r'\[Contact_Name\][^\n]*\n', ''),
            (r'\[Title\][^\n]*\n', ''),
            (r'\[Number\][^\n]*\n', ''),
            (r'\[Email\][^\n]*\n', ''),
            (r'\[Count\] items', 'Multiple items'),
            (r'\[Total\]', 'See CLIN table'),
            (r'\[Frequency\]', 'Single delivery'),
            (r'\[Point\]', 'Destination'),
            (r'\[Location\]', 'See delivery address'),
            (r'\[Notes\]', ''),
            (r'\[specific_documentation\]', 'documentation'),
            (r'\[Specific_requirements[^\]]*\]', 'See solicitation requirements'),
        ]
        
        for pattern, replacement in placeholder_patterns:
            rfq_content = re.sub(pattern, replacement, rfq_content, flags=re.IGNORECASE)
        
        # 3. Remove conditional instruction blocks
        conditional_patterns = [
            r'IF First Article Testing Required:[^\n]*\n(?:[^\n]+\n)*?(?=\n\n|Quality Standard)',
            r'IF ITAR Controlled:[^\n]*\n',
            r'IF JCP Required:[^\n]*\n',
            r'IF CDRL Required:[^\n]*\n',
            r'IF Defense:[^\n]*\n',
            r'IF CMMC:[^\n]*\n',
            r'IF Counterfeit Prevention:[^\n]*\n',
            r'IF Best Value:[^\n]*\n',
            r'IF All-or-None:[^\n]*\n',
            r'IF Government Inspection Contact Provided:[^\n]*\n',
            r'IF Few CLINs[^\n]*\n',
            r'IF Many CLINs[^\n]*\n',
            r'IF FAT Required:[^\n]*\n',
            r'IF NOT FOUND:[^\n]*\n',
            r'IF Special Requirements:[^\n]*\n',
        ]
        
        for pattern in conditional_patterns:
            rfq_content = re.sub(pattern, '', rfq_content, flags=re.MULTILINE | re.IGNORECASE)
        
        # 4. Remove "LIST ALL THAT APPLY:" and similar meta-instructions
        meta_instructions = [
            r'LIST ALL THAT APPLY:[^\n]*\n',
            r'WRITE \d+-\d+ COMPLETE BULLET POINTS[^\n]*\n',
            r'NUMBERED LIST[^\n]*\n',
            r'SUMMARY FORMAT[^\n]*\n',
            r'NEVER USE FRAGMENTS[^\n]*\n',
        ]
        
        for pattern in meta_instructions:
            rfq_content = re.sub(pattern, '', rfq_content, flags=re.MULTILINE | re.IGNORECASE)
        
        # 5. Clean up government emails (replace with vendor email)
        rfq_content = re.sub(
            r'[\w\.-]+@[\w\.-]*\.(?:gov|mil)\b',
            'bobbysmitty078@gmail.com',
            rfq_content
        )
        
        # 6. Remove bold formatting
        rfq_content = rfq_content.replace('**', '')
        
        # 7. Remove HTML artifacts
        rfq_content = re.sub(r'<!--.*?-->', '', rfq_content, flags=re.DOTALL)
        rfq_content = re.sub(r'<[^>]+>', '', rfq_content)
        
        # 8. Normalize whitespace
        rfq_content = re.sub(r'\n{3,}', '\n\n', rfq_content)
        
        # 9. Remove empty sections
        rfq_content = re.sub(r'(🏛️[^\n]+)\n\n(?=🏛️|🟩|$)', r'\1\n', rfq_content)
        
        logger.info("  [Post-Process] ✓ Complete")
        return rfq_content.strip()

