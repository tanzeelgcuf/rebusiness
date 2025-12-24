
import os
import sys
import time
import logging
import json

# Add ai_agents path
sys.path.append(os.path.abspath('ai_agents'))

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def run_backfill(limit=50):
    logger.info("--- Starting Deep Digging Backfill ---")
    
    db_manager = DatabaseManager()
    
    # 1. Identify Candidates: prioritize those with low confidence or missing products
    # We will just take recent ones for now, or those with confidence < 0.8
    conn = db_manager._connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT contract_id, url, title 
        FROM solicitations 
        WHERE (extraction_confidence < 0.8 OR extraction_confidence IS NULL)
        ORDER BY created_at DESC 
        LIMIT ?
    """, (limit,))
    candidates = cursor.fetchall()
    db_manager._close_db()
    
    if not candidates:
        logger.info("No candidates found for backfill.")
        return

    logger.info(f"Found {len(candidates)} candidates for Deep Digging refinement.")

    downloader = SamGovAgent()
    reader = AttachmentReaderAgent()

    try:
        for i, row in enumerate(candidates):
            contract_id = row['contract_id']
            url = row['url']
            title = row['title']
            
            try:
                logger.info(f"[{i+1}/{len(candidates)}] Processing {contract_id}: {title}")
                
                # A. Deep Fetch (check for new links/files)
                try:
                    downloader.process_detail_page(url)
                except Exception as e:
                    logger.error(f"  Error download/crawling {url}: {e}")
                    continue

                # B. Clear Old Products
                db_manager.clear_products_for_solicitation(contract_id)

                # C. Deep Analysis (Reader Agent)
                try:
                    analysis = reader.create_summary_report(contract_id)
                except Exception as e:
                    logger.error(f"  Critical Analysis Error for {contract_id}: {e}")
                    continue
                
                if "error" in analysis:
                    logger.error(f"  Analysis failed: {analysis['error']}")
                else:
                    db_manager.add_solicitation_analysis(contract_id, json.dumps(analysis), confidence=0.95, review_status='pending')
                    prod_count = len(analysis.get('product_details', []))
                    logger.info(f"  Success! Re-extracted {prod_count} products.")
                
            except Exception as e:
                logger.error(f"  Unexpected error for {contract_id}: {e}")

            time.sleep(2) # Polite delay

    finally:
        downloader.close()
        logger.info("--- Backfill Complete ---")

if __name__ == "__main__":
    # Allow passing limit as arg
    limit = 50
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except: pass
    
    run_backfill(limit)
