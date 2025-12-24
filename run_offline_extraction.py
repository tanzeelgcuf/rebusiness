
import os
import sys
import logging
import sqlite3
import json
import datetime
from collections import defaultdict

# Add parent directory to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from database_manager import DatabaseManager
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OfflineExtraction")

DOWNLOADS_DIR = "downloads"

def scan_downloads_for_contract(contract_id, downloads_dir):
    """
    Scans the download directory for files containing the contract_id.
    Returns a list of (filename, absolute_path).
    """
    matches = []
    if not os.path.exists(downloads_dir):
        return matches

    for f in os.listdir(downloads_dir):
        # Case insensitive match or exact containment
        if contract_id in f:
             matches.append((f, os.path.abspath(os.path.join(downloads_dir, f))))
    
    return matches

def main():
    logger.info("--- Starting Offline Product Extraction ---")
    
    db_manager = DatabaseManager()
    reader_agent = AttachmentReaderAgent()
    
    # 1. Get solicitations needing analysis
    logger.info("Identifying pending solicitations...")
    conn = db_manager._connect_db()
    cursor = conn.cursor()
    
    # Select solicitations that exist but have NO entry in solicitation_analysis OR have NULL analysis_json
    cursor.execute("""
        SELECT s.contract_id 
        FROM solicitations s
        LEFT JOIN solicitation_analysis sa ON s.contract_id = sa.contract_id
        WHERE sa.analysis_json IS NULL
    """)
    pending_ids = [row[0] for row in cursor.fetchall()]
    db_manager._close_db()
    
    logger.info(f"Found {len(pending_ids)} solicitations pending analysis.")
    
    if not pending_ids:
        return

    processed_count = 0
    
    for i, contract_id in enumerate(pending_ids):
        logger.info(f"[{i+1}/{len(pending_ids)}] Processing {contract_id}...")
        
        # 2. Backfill Attachments
        found_files = scan_downloads_for_contract(contract_id, DOWNLOADS_DIR)
        
        if found_files:
            logger.info(f"  Found {len(found_files)} matching files in downloads.")
            
            # Check what's already in DB
            existing_attachments = db_manager.get_attachments_for_solicitation(contract_id)
            existing_names = {a['file_name'] for a in existing_attachments}
            
            for fname, fpath in found_files:
                if fname not in existing_names:
                    logger.info(f"  Registering new attachment: {fname}")
                    try:
                        db_manager.add_attachment(
                            contract_id=contract_id,
                            file_name=fname,
                            file_path=fpath,
                            url="local_scan_offline",
                            download_date=datetime.datetime.now().isoformat()
                        )
                    except Exception as e:
                        logger.error(f"  Failed to register {fname}: {e}")
        else:
             logger.info("  No local matching files found.")

        # 3. Run Extraction (if there are attachments now)
        # Check attachments again (re-query to include just added ones)
        current_attachments = db_manager.get_attachments_for_solicitation(contract_id)
        
        if not current_attachments:
            logger.info(f"  No attachments for {contract_id}. Proceeding with text-only analysis.")
            
        try:
            logger.info("  Running AI Analysis...")
            analysis_result = reader_agent.create_summary_report(contract_id)
            
            if "error" in analysis_result:
                logger.error(f"  Analysis failed: {analysis_result['error']}")
            else:
                # Save result
                db_manager.add_solicitation_analysis(contract_id, json.dumps(analysis_result))
                
                prod_count = len(analysis_result.get('product_details', []))
                logger.info(f"  Success: Extracted {prod_count} products.")
                processed_count += 1
                
        except Exception as e:
             logger.error(f"  Critical error analyzing {contract_id}: {e}")

    logger.info("--- Offline Extraction Complete ---")
    logger.info(f"Successfully processed {processed_count} solicitations.")

if __name__ == "__main__":
    main()
