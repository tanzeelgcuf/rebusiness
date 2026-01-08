import os
import sys
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import google.generativeai as genai
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
            genai.configure(api_key=config.GEMINI_API_KEY)
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
            else:
                logger.warning(f"Unsupported file type: {ext}")
                return None
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None
    
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
                file_ref = genai.upload_file(file_path, mime_type="application/pdf")
                return file_ref
            except Exception as e:
                logger.error(f"Gemini upload failed: {e}")
        
        return full_text if full_text.strip() else "Could not extract PDF content."
    
    def _read_text_file(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def _read_docx_file(self, file_path: str) -> str:
        from docx import Document
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    
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
        vendor_email: str = "john@campsable.com",
        organization_name: str = "Camp Sable, LLC"
    ) -> Dict:
        """
        Enhanced RFQ generation with 100% template fidelity.
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"RFQ GENERATION: {contract_id}")
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
        
        # Step 5: Generate RFQ
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
        logger.info(f"{'='*80}\n")
        
        return {
            "rfq_content": rfq_content,
            "rfq_type": final_type,
            "files_processed": file_count,
            "success": True
        }
    
    def _generate_rfq_with_llm(
        self,
        content_parts: List,
        rfq_type: str,
        camp_deadline: Optional[str],
        internal_deadline_offset: int
    ) -> Dict:
        """Generate RFQ using Gemini with template prompts."""
        
        # Select prompt
        if rfq_type == "PRODUCT":
            system_instruction = PRODUCT_RFQ_PROMPT
        else:
            system_instruction = SERVICE_RFQ_PROMPT
        
        # Inject deadline instruction
        if camp_deadline:
            system_instruction += f"\n\nCRITICAL: The internal deadline for Camp Sable is **{camp_deadline}**. USE THIS EXACT DATE where it says 'Your response is needed on or before...'."
        else:
            system_instruction += f"\n\nCRITICAL: Calculate deadline by subtracting {internal_deadline_offset} BUSINESS DAYS (skip weekends) from the government due date."
        
        logger.info(f"  [LLM] Generating {rfq_type} RFQ...")
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            # Build message
            message_parts = [system_instruction]
            message_parts.extend(content_parts)
            
            # Generate
            response = model.generate_content(message_parts)
            rfq_markdown = response.text
            
            if not rfq_markdown or len(rfq_markdown) < 500:
                return {"error": f"LLM response too short ({len(rfq_markdown)} chars)"}
            
            logger.info(f"  [LLM] ✓ Generated {len(rfq_markdown)} chars")
            
            return {
                "rfq_content": rfq_markdown,
                "rfq_type": rfq_type,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"  [LLM] ✗ Error: {e}")
            return {"error": str(e)}
    
    def _post_process_rfq(self, rfq_content: str) -> str:
        """
        Post-processing: Clean and sanitize RFQ content.
        CRITICAL for 100% template compliance.
        """
        logger.info(f"  [Post-Process] Cleaning RFQ...")
        
        # 1. Remove government emails (CRITICAL)
        gov_email_patterns = [
            r'[\w\.-]+@[\w\.-]*\.mil\b',
            r'[\w\.-]+@[\w\.-]*\.gov\b',
        ]
        
        for pattern in gov_email_patterns:
            rfq_content = re.sub(pattern, 'john@campsable.com', rfq_content, flags=re.IGNORECASE)
        
        # 2. Remove bold formatting
        rfq_content = rfq_content.replace("**", "")
        
        # 3. Remove HTML artifacts
        rfq_content = re.sub(r'<!--.*?-->', '', rfq_content, flags=re.DOTALL)
        rfq_content = re.sub(r'<[^>]+>', '', rfq_content)
        
        # 4. Normalize whitespace
        rfq_content = re.sub(r'\n{3,}', '\n\n', rfq_content)
        
        logger.info(f"  [Post-Process] ✓ Complete")
        
        return rfq_content
