import logging
import sys
import os
import json

# Add path for agents
sys.path.append(os.path.abspath('ai_agents'))

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager
import google.generativeai as genai # Need to use gemini directly for custom QA

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Researcher")

CONTRACT_IDS = ['214d53a25f', 'ab292d676d']
QUESTION = "What is the thickness of the Fiber-Reinforced Polymer (FRP) Mat? Is it a plate? Provide any thickness dimensions found."

def research_question():
    downloader = SamGovAgent()
    reader = AttachmentReaderAgent()
    db_manager = DatabaseManager()
    
    for contract_id in CONTRACT_IDS:
        logger.info(f"--- Researching {contract_id} ---")
        
        # 1. Fetch URL associated (Need to get from DB)
        # solicitation = db_manager.get_solicitation(contract_id) 
        # Manual SQL fallback
        import sqlite3
        conn = sqlite3.connect("rebusiness_automation.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM solicitations WHERE contract_id = ?", (contract_id,))
        solicitation = cur.fetchone()
        conn.close()

        if not solicitation:
            logger.info("Solicitation not found in DB.")
            continue
            
        url = solicitation['url']
        logger.info(f"  URL: {url}")
        
        # 2. Deep Fetch (Refresh files)
        try:
            downloader.process_detail_page(url)
        except: pass
        
        # 3. Read Files (Direct from Disk)
        base_dir = f"data/solicitations/{contract_id}/attachments"
        if not os.path.exists(base_dir):
             logger.info(f"  Directory not found: {base_dir}")
             continue
             
        file_list = [f for f in os.listdir(base_dir) if os.path.isfile(os.path.join(base_dir, f))]
        
        content_parts = []
        for i, filename in enumerate(file_list):
            path = os.path.join(base_dir, filename)
            # Skip zip files for now unless we unzip them, but let's try reading PDFs first
            if filename.endswith('.zip'): continue 
            
            logger.info(f"  Reading {filename}...")
            content = reader._read_file_content(path)
            if content:
                if isinstance(content, str):
                    content_parts.append(f"Document {i}: {filename}\n{content}")
                else:
                    content_parts.append(f"Document {i}: {filename}")
                    content_parts.append(content)

        if not content_parts:
            logger.info("  No content found.")
            continue
            
        # 4. Ask Gemini
        logger.info(f"  Asking Gemini: {QUESTION}")
        
        # Create a custom prompt
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt_parts = ["""
        You are a technical procurement analyst. Review the provided solicitation documents and answer the user's specific question.
        
        Question:
        """]
        prompt_parts.append(QUESTION)
        prompt_parts.append("""
        
        Documents:
        """)
        prompt_parts.extend(content_parts)
        
        prompt_parts.append("""
        
        Answer:
        """)
        
        try:
            response = model.generate_content(prompt_parts)
            print(f"\n\n=== ANSWER FOR {contract_id} ===\n{response.text}\n===============================\n")
        except Exception as e:
            logger.error(f"  Gemini Error: {e}")

    downloader.close()

if __name__ == "__main__":
    research_question()
