import sqlite3
import logging
import time

# Configuration
DB_PATH = "rebusiness_automation.db"

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_pending_requests():
    """
    Creates 'pending' manufacturer_requests for all manufacturers that:
    1. Have a valid email.
    2. Are linked to a product in `product_suppliers`.
    3. Do NOT already have a request for that product in `manufacturer_requests`.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    logger.info("--- Generating Pending Requests for Valid Emails ---")

    # Select all valid Manufacturer-Product pairs
    # QUALITY GATE: Only include products from solicitations that have PDF attachments
    # This ensures we only send emails with complete, detailed information
    query = """
        SELECT ps.product_id, ps.manufacturer_id, m.name
        FROM product_suppliers ps
        JOIN manufacturers m ON ps.manufacturer_id = m.id
        JOIN products p ON ps.product_id = p.id
        JOIN solicitations s ON p.contract_id = s.contract_id
        WHERE m.email IS NOT NULL AND m.email != ''
          AND EXISTS (
              SELECT 1 FROM attachments a 
              WHERE a.contract_id = s.contract_id
          )
    """
    cursor.execute(query)
    all_pairs = cursor.fetchall()
    
    logger.info(f"Found {len(all_pairs)} potential manufacturer-product links with emails.")

    created_count = 0
    
    for pair in all_pairs:
        product_id, manufacturer_id, mfg_name = pair
        
        # Check if request already exists
        cursor.execute("""
            SELECT id FROM manufacturer_requests 
            WHERE product_id = ? AND manufacturer_id = ?
        """, (product_id, manufacturer_id))
        
        if not cursor.fetchone():
            # Create Request
            try:
                cursor.execute("""
                    INSERT INTO manufacturer_requests (manufacturer_id, product_id, status, method)
                    VALUES (?, ?, 'pending', 'email')
                """, (manufacturer_id, product_id))
                created_count += 1
            except Exception as e:
                logger.error(f"Error creating request for {mfg_name}: {e}")

    conn.commit()
    conn.close()
    
    logger.info(f"--- Generation Complete. Created {created_count} new pending requests. ---")

if __name__ == "__main__":
    generate_pending_requests()
