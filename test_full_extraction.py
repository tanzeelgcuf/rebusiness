import sqlite3
import json
import logging
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_random_extraction():
    db_manager = DatabaseManager()
    
    conn = db_manager._connect_db()
    cursor = conn.cursor()
    
    # correct query to find a solicitation that HAS attachments
    query = """
        SELECT s.contract_id 
        FROM solicitations s
        JOIN attachments a ON s.contract_id = a.contract_id
        ORDER BY s.id DESC
        LIMIT 1
    """
    cursor.execute(query)
    row = cursor.fetchone()
    db_manager._close_db()
    
    if not row:
        logger.error("No solicitations with attachments found in DB to test!")
        return

    contract_id = row[0]
    logger.info(f"--- TESTING EXTRACTION ON: {contract_id} ---")
    
    agent = AttachmentReaderAgent()
    
    # Force re-analysis even if exists
    analysis = agent.create_summary_report(contract_id)
    
    print("\n" + "="*60)
    print(f"FULL EXTRACTION RESULT FOR {contract_id}")
    print("="*60)
    print(json.dumps(analysis, indent=2))
    print("="*60 + "\n")
    
    # Verification Check
    p_details = analysis.get('product_details', [])
    clins = analysis.get('clins', [])
    
    if p_details and len(p_details) > 0:
        print("✅ Product Details Extracted")
        print(f"   Name: {p_details[0].get('name')}")
        print(f"   Specs: {p_details[0].get('specifications')}")
    else:
        print("⚠️  No Product Details found (might be Service?)")

    if clins:
        print(f"✅ CLINs Extracted ({len(clins)} found)")
    else:
        print("⚠️  No CLINs found")
        
    print(f"✅ Packaging: {analysis.get('packaging_requirements')}")
    print(f"✅ Inspection: {analysis.get('inspection_testing')}")

if __name__ == "__main__":
    test_random_extraction()
