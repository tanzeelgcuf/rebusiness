
import logging
import sys
import os
import json
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from database_manager import DatabaseManager
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from utils.doc_converter import convert_md_to_docx

def run_verification(contract_id="df99825aadd543aab5cfafbbf0daeea1"):
    logger.info(f"Starting direct verification for {contract_id}")
    
    reader = AttachmentReaderAgent()
    
    # Run generation with strict fidelity
    result = reader.create_summary_report(
        contract_id,
        skip_json=True,
        strict_fidelity=True,
        template_type="SERVICE" # Enforce SERVICE
    )
    
    if "error" in result:
        logger.error(f"Generation failed: {result['error']}")
        return
        
    rfq_content = result.get("rfq_content")
    if not rfq_content:
        logger.error("No content returned")
        return
        
    # Save MD
    output_dir = os.path.join("rfq_downloads", "2026-01-09")
    os.makedirs(output_dir, exist_ok=True)
    md_path = os.path.join(output_dir, f"{contract_id}_RFQ_SERVICE_verified.md")
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(rfq_content)
    logger.info(f"Saved MD to {md_path}")
    
    # Convert to DOCX
    docx_path = md_path.replace(".md", ".docx")
    if convert_md_to_docx(rfq_content, docx_path):
        logger.info(f"Saved DOCX to {docx_path}")
    else:
        logger.error("DOCX conversion failed")

if __name__ == "__main__":
    run_verification()
