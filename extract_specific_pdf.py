
import asyncio
import os
import logging
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def extract_pdf_content():
    db_manager = DatabaseManager()
    agent = AttachmentReaderAgent()
    
    file_path = "/Users/apple/Downloads/rebusinessautomationproject/downloads/PWS_Combined Pest Control FY26 1.pdf"
    
    if os.path.exists(file_path):
        logger.info(f"Processing file: {file_path}")
        # We can use the internal method _read_file_content if we want just text, 
        # or _analyze_content_with_llm if we want the AI extraction.
        # Let's try to get the AI analysis directly as that's what we want (CLINs).
        
        # We need to simulate the solicitation context slightly or just pass generic prompt
        solicitation_data = {
            "title": "Combined Pest Control",
            "description": "Pest control services in Buzzards Bay, MA"
        }
        
        # Use the public method create_summary_report logic, but applied to single file
        # Reading file content first
        content = agent._read_file_content(file_path) # Removed await and contract ID argument
        
        if content:
            logger.info("File content read successfully. Sending to LLM...")
            # We want specific extraction of CLINs and products
            analysis = agent._analyze_content_with_llm([content]) # Removed await and wrapped content in list
            print("\n\n--- EXTRACTED ANALYSIS ---\n")
            print(analysis)
            print("\n--------------------------\n")
        else:
            logger.error("Failed to read file content.")
    else:
        logger.error(f"File not found at {file_path}")

if __name__ == "__main__":
    asyncio.run(extract_pdf_content())
