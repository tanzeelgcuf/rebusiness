import sys
from unittest.mock import MagicMock

# Mock-Shim
sys.modules['google.generativeai'] = MagicMock()
sys.modules['google.ai.generativelanguage'] = MagicMock()
sys.modules['google.api_core'] = MagicMock()

import asyncio
import sqlite3
from database_manager import DatabaseManager
from ai_agents.OutreachAgent.form_filler import FormFiller

async def run_batch_backfill():
    db = DatabaseManager()
    outreach_agent = FormFiller()
    
    print("=== Starting Batch Outreach Backfill ===")
    
    while True:
        conn = db._connect_db()
        cursor = conn.cursor()
        
        # Query: Manufacturers linked to products, that are NOT in manufacturer_requests
        # Join products to get product details (needed for outreach context)
        # Limit 50 to process efficiently
        # Schema: products(id, contract_id, product_name, description...)
        # product_suppliers(product_id, manufacturer_id)
        query = """
            SELECT m.id, m.name, m.website, p.product_name, p.description, p.id
            FROM manufacturers m
            JOIN product_suppliers ps ON m.id = ps.manufacturer_id
            JOIN products p ON ps.product_id = p.id
            WHERE m.id NOT IN (SELECT manufacturer_id FROM manufacturer_requests)
            LIMIT 50
        """
        
        candidates = cursor.execute(query).fetchall()
        db._close_db() # Free/reset connection
        
        if not candidates:
            print("No more uncontacted manufacturers found. Backfill complete.")
            break
            
        print(f"--- Processing Batch of {len(candidates)} Manufacturers ---")
        
        for row in candidates:
            m_id, name, website, p_name, p_desc, p_id = row
            
            print(f">>> Engaging {name} (ID: {m_id}) for '{p_name}'")
            
            product_details = {
                'product_name': p_name,
                'description': p_desc or f"Inquiry regarding {p_name}",
            }
            
            try:
                # 1. Outreach
                result = await outreach_agent.process_supplier_outreach(website, product_details)
                
                # 2. Log Result to DB
                status = 'sent' if result.get('success') else 'failed'
                
                conn = db._connect_db()
                c = conn.cursor()
                c.execute("""
                    INSERT INTO manufacturer_requests (manufacturer_id, product_id, status, request_date, response_date)
                    VALUES (?, ?, ?, datetime('now'), NULL)
                """, (m_id, p_id, status))
                conn.commit()
                db._close_db()
                print(f"  Logged status: {status}")
                
            except Exception as e:
                print(f"Error processing {name}: {e}")
                
        # Small sleep between batches
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_batch_backfill())
