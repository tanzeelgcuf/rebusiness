import sqlite3
import time
import logging
from database_manager import DatabaseManager
from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('enrichment.log')
    ]
)
logger = logging.getLogger("BatchEnrichment")

def batch_enrich_emails(batch_size=50):
    db = DatabaseManager()
    agent = ThomasNetAgent()
    
    conn = db._connect_db()
    cursor = conn.cursor()
    
    # 1. Select manufacturers with missing emails, prioritizing those not recently updated
    # AND where we have a website url to bypass search
    query = """
        SELECT id, name, website 
        FROM manufacturers 
        WHERE (email IS NULL OR email = '')
          AND (website IS NOT NULL AND website != '')
          AND (updated_at IS NULL OR updated_at < datetime('now', '-1 hour'))
        ORDER BY created_at DESC
        LIMIT ?
    """
    
    cursor.execute(query, (batch_size,))
    rows = cursor.fetchall()
    
    if not rows:
        logger.info("No manufacturers found needing enrichment (or all recently attempted).")
        return
        
    logger.info(f"--- Starting Enrichment for {len(rows)} Manufacturers ---")
    
    success_count = 0
    
    for i, (mfg_id, name, known_website) in enumerate(rows):
        logger.info(f"[{i+1}/{len(rows)}] Enriching: {name} (ID: {mfg_id}) - URL: {known_website}")
        
        try:
            # Call the internal method with known_website
            result = agent._enrich_supplier_details(name, "General Sourcing", known_website=known_website)
            
            if result and result.get('email'):
                email = result['email']
                website = result.get('website')
                phone = result.get('phone')
                
                logger.info(f"  > SUCCESS: Found {email} ({website})")
                
                # Update DB with success
                update_sql = """
                    UPDATE manufacturers 
                    SET email = ?, website = COALESCE(?, website), phone = COALESCE(?, phone), updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """
                cursor.execute(update_sql, (email, website, phone, mfg_id))
                success_count += 1
            else:
                logger.info("  > No email found.")
                # Update timestamp to mark as attempted so we don't pick it up again immediately
                cursor.execute("UPDATE manufacturers SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (mfg_id,))
            
            conn.commit()
                
        except Exception as e:
            logger.error(f"  > Error processing {name}: {e}")
            # Even on error, update timestamp to unblock queue
            try:
                cursor.execute("UPDATE manufacturers SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (mfg_id,))
                conn.commit()
            except: pass
            
        # Rate limit kindness
        time.sleep(2)
        
    conn.close()
    logger.info(f"--- Batch Complete. Enriched {success_count}/{len(rows)} ---")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50, help="Number of records to process")
    args = parser.parse_args()
    
    batch_enrich_emails(args.limit)
