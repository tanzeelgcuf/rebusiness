
"""
Complete end-to-end extraction pipeline for SAM.gov solicitations.
Orchestrates scraping, AI extraction, strict validation, and targeted repair.
"""

import json
import os
import sys
import logging
import time
import re
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from ai_agents.SAMGovExtractor.prompts import (
    SYSTEM_PROMPT, 
    DETECTION_PROMPT,
    PRODUCT_EXTRACTION_PROMPT,
    SERVICE_EXTRACTION_PROMPT,
    PRIMARY_EXTRACTION_PROMPT, 
    ATTACHMENT_DEEP_DIVE_PROMPT, 
    VERIFICATION_PROMPT,
    TARGETED_CLIN_PROMPT,
    TARGETED_ADDRESS_PROMPT
)
from ai_agents.SAMGovExtractor.validator import SolicitationValidator

# Gemini / Google GenAI
import config
import google.generativeai as genai

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SAMGovExtractor")

class SAMGovExtractor:
    """
    Main controller for strict solicitation extraction.
    """
    
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        if not self.api_key:
             logger.error("GEMINI_API_KEY not found in config.py.")
             raise ValueError("GEMINI_API_KEY missing")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash', 
                                           generation_config={"response_mime_type": "application/json"})
        
    def extract_solicitation(self, 
                             html_content: str, 
                             attachments: List[Dict[str, Any]] = []) -> Dict[str, Any]:
        """
        Extracts data with category-aware logic and strict quality gates.
        """
        logger.info(f"🚀 Starting extraction pipeline for document (Length: {len(html_content)})")
        
        # Phase 0: Pre-processing (Clean HTML)
        clean_content = self._clean_text(html_content)
        logger.info(f"     - Document cleaned (New Length: {len(clean_content)})")

        # Step 1: Category Detection
        logger.info("  🔍 Phase 0: Detecting Solicitation Category...")
        detection_res = self._call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=DETECTION_PROMPT.format(document_text=clean_content[:5000])
        )
        category = detection_res.get('category', 'Product')
        logger.info(f"     - Detected Category: {category}")

        # Select Prompt
        extraction_prompt = SERVICE_EXTRACTION_PROMPT if category == "Service" else PRODUCT_EXTRACTION_PROMPT
        
        # Step 2: Primary Extraction (Main Text)
        logger.info(f"  📄 Phase 1: Extracting from Main Solicitation Text (Mode: {category})...")
        main_data = self._call_llm(
             system_prompt=SYSTEM_PROMPT,
             user_prompt=extraction_prompt.format(document_text=clean_content[:40000])
        )
        main_data['solicitation_category'] = category
        
        # ... (rest of the method) ...
        
        # Step 3: Attachment Deep Dive
        if attachments:
            logger.info(f"  📎 Phase 2: Processing {len(attachments)} attachments...")
            for att in attachments:
                att_filename = att.get('filename')
                att_content = att.get('content')
                
                if not att_content:
                    logger.warning(f"    - Skipping empty attachment: {att_filename}")
                    continue
                
                logger.info(f"    - Analyzing: {att_filename}")
                att_data = self._call_llm(
                     system_prompt=SYSTEM_PROMPT,
                     user_prompt=ATTACHMENT_DEEP_DIVE_PROMPT.format(
                         filename=att_filename,
                         document_type="Attachment",
                         content=att_content[:30000]
                     )
                )
                
                # Merge Attachment Data
                self._merge_data(main_data, att_data)
        
        # Step 4: Validation
        logger.info("  🔍 Phase 3: Validating Extracted Data...")
        is_valid, errors = SolicitationValidator.validate(main_data)
        
        if not is_valid:
            logger.warning(f"  ❌ Validation Failed: {len(errors)} errors found.")
            for e in errors: logger.warning(f"     - {e}")
            
            # Step 5: Targeted Repair
            logger.info("  🔧 Phase 4: Attempting Targeted Repair...")
            main_data = self._repair_data(main_data, errors, html_content, attachments)
            
            # Re-Validate
            is_valid, final_errors = SolicitationValidator.validate(main_data)
            if not is_valid:
                 logger.error("  ❌ Repair failed. Returning Incomplete Data.")
                 main_data['extraction_status'] = "FAILED"
                 main_data['validation_errors'] = final_errors
            else:
                 logger.info("  ✅ Repair successful!")
                 main_data['extraction_status'] = "SUCCESS"
        else:
            logger.info("  ✅ Data is Valid.")
            main_data['extraction_status'] = "SUCCESS"
            
        return main_data

    def _clean_text(self, text: str) -> str:
        """Strips HTML, scripts, and styles to provide clean text to the LLM."""
        if not text: return ""
        
        # Strip scripts and styles
        text = re.sub(r'<(script|style).*?>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Strip HTML tags
        text = re.sub(r'<.*?>', ' ', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Dict:
        """Helper to call Gemini and parse JSON safely."""
        try:
            response = self.model.generate_content([system_prompt, user_prompt])
            text = response.text.strip()
            
            # Clean possible markdown code blocks
            if text.startswith("```json"):
                text = text.replace("```json", "", 1).replace("```", "", 1).strip()
            elif text.startswith("```"):
                text = text.replace("```", "", 1).replace("```", "", 1).strip()
                
            res = json.loads(text)
            
            if isinstance(res, list):
                logger.warning("LLM returned a list. Wrapping in dict.")
                return {"items": res}
            
            return res
        except Exception as e:
            logger.error(f"LLM Call Failed: {e}")
            if 'response' in locals() and hasattr(response, 'text'):
                logger.debug(f"RAW LLM RESPONSE: {response.text}")
            return {}

    def _merge_data(self, main: Dict, new: Dict):
        """Merges new data into main dict, preferring non-empty/non-placeholder values."""
        
        # Simple recursive merge for now
        for k, v in new.items():
            if not v: continue
            
            # If main doesn't have it, or main has placeholder
            if k not in main or not main[k] or SolicitationValidator._contains_placeholder(str(main[k])):
                main[k] = v
            # Special handling for delivery_requirements dict
            elif k == "delivery_requirements" and isinstance(v, dict):
                 if "delivery_requirements" not in main: main["delivery_requirements"] = {}
                 for dk, dv in v.items():
                     if dv and not SolicitationValidator._contains_placeholder(str(dv)):
                         main["delivery_requirements"][dk] = dv
            # Special handling for CLINs? Maybe later.

    def _repair_data(self, data: Dict, errors: List[str], html: str, attachments: List[Dict]) -> Dict:
        """
        Orchestrates specific repair prompts based on error types.
        """
        # Combine all text for context
        all_text = html + "\n\n"
        for att in attachments:
            all_text += f"\n--- {att['filename']} ---\n{att.get('content','')}"

        # 1. Missing CLINs?
        if any("CLIN" in e for e in errors):
             logger.info("    -> Repairing CLINs...")
             clin_data = self._call_llm(SYSTEM_PROMPT, TARGETED_CLIN_PROMPT.format(document_text=all_text[:80000]))
             if clin_data.get('clins'):
                 data['clins'] = clin_data['clins']

        # 2. Missing Address?
        if any("Address" in e or "Location" in e for e in errors):
             logger.info("    -> Repairing Address...")
             # Targeted prompt returns a string usually, but we asked for JSON in system config? 
             # Actually prompts.py TARGETED_ADDRESS_PROMPT returns a specific string in the description 
             # but our model is configured for JSON. Let's assume it returns { "address": ... } ideally.
             # Let's verify response structure.
             
             # Actually, let's just use the General Verification Prompt which is more flexible
             pass 

        # 3. General "Catch-All" Verification
        logger.info("    -> Running General Verification/Repair...")
        repaired_data = self._call_llm(
             system_prompt=SYSTEM_PROMPT,
             user_prompt=VERIFICATION_PROMPT.format(
                 category=data.get('solicitation_category', 'Product'),
                 extracted_data=json.dumps(data, indent=2),
                 document_text=all_text[:80000]
             )
        )
        
        # Merge repair
        self._merge_data(data, repaired_data)
        
        return data

if __name__ == "__main__":
    # Test stub
    pass
