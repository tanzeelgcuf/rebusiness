import os
import sys
import time
import random
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_manager import DatabaseManager
from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent
from ai_agents.OutreachAgent.outreach_agent import OutreachAgent

# Configuration
MIN_SUPPLIERS = 5
MAX_SUPPLIERS = 20

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OutreachCoordinator:
    def __init__(self):
        self.db = DatabaseManager()
        self.thomasnet_agent = ThomasNetAgent()
        self.outreach_agent = OutreachAgent(self.db)
        
    def run_pipeline(self):
        logger.info("Starting Product Outreach Backfill Pipeline...")
        
        while True:
            # 1. Get products that need attention from the backlog
            products = self.db.get_products_for_sourcing(limit=1)
            
            if not products:
                logger.info("No more products pending sourcing in the backlog. Sleeping...")
                time.sleep(60)
                continue
                
            product = products[0]
            product_id = product['id']
            
            # Fetch contract_id safely
            conn = self.db._connect_db()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT contract_id FROM products WHERE id = ?", (product_id,))
                row = cursor.fetchone()
                contract_id = row[0] if row else None
            finally:
                self.db._close_db()
            
            product_name = product['product_name']
            logger.info(f"Processing Backlog Product: {product_name} (ID: {product_id}, Contract: {contract_id})")
            
            # Check current status
            status_info = self.db.get_sourcing_status(product_id) or {}
            suppliers_found_log = status_info.get('suppliers_found_count', 0)
            
            # Check existing vendors
            existing_vendors = self.db.get_vendors_for_solicitation(contract_id)
            real_vendor_count = len(existing_vendors)
            
            # --- PHASE 1: SOURCING ---
            if real_vendor_count < MIN_SUPPLIERS:
                logger.info(f"Phase 1: Sourcing needed (Current: {real_vendor_count}, Log: {suppliers_found_log})")
                
                try:
                    suppliers = self.thomasnet_agent.find_suppliers_for_product({'product_name': product_name})
                    added_count = 0
                    
                    for s in suppliers:
                        if self.db.add_vendor(
                            contract_id=contract_id,
                            name=s['name'],
                            website=s['website'],
                            email=s.get('email'),
                            phone=s.get('phone'),
                            confidence_score=90, 
                            has_gov_page=False,
                            has_past_performance=False,
                            gov_agencies_worked_with=None,
                            past_performance_summary=s.get('notes', 'Sourced via ThomasNet (Backfill)'),
                            key_personnel=None,
                            linkedin_url=None,
                            place_types=None,
                            email_status='Ready to Contact'
                        ):
                            added_count += 1
                    
                    if added_count > 0:
                        self.db.update_sourcing_status(product_id, status='sourcing', found_inc=added_count)
                        logger.info(f"  Found and added {added_count} new vendors.")
                    else:
                        # If we found nothing new, mark 'sourcing_complete' to avoid infinite attempts on this item
                        logger.info("  No new vendors found. Marking sourcing as complete to move on.")
                        self.db.update_sourcing_status(product_id, status='sourcing_complete')
                        
                except Exception as e:
                    logger.error(f"Sourcing failed for {product_name}: {e}")
                    time.sleep(5)
            else:
                logger.info("  Sufficient vendors exist. Marking sourcing complete.")
                self.db.update_sourcing_status(product_id, status='sourcing_complete')

            # --- PHASE 2: OUTREACH ---
            # Fetch candidates and CONVERT TO DICT (Fix for sqlite3.Row error)
            raw_candidates = [v for v in self.db.get_vendors_for_solicitation(contract_id) if v['email_status'] == 'Ready to Contact']
            candidates = [dict(r) for r in raw_candidates]
            
            outreach_count = 0
            MAX_BATCH = 5
            
            if candidates:
                logger.info(f"Phase 2: Outreach candidates found: {len(candidates)}")
                for candidate in candidates[:MAX_BATCH]:
                    logger.info(f"  Contacting: {candidate['name']}...")
                    
                    details = {
                        "product_name": product_name,
                        "quantity": product.get('quantity'),
                        "specifications": product.get('specifications'),
                        "description": product.get('description'),
                        "contract_id": contract_id
                    }
                    
                    try:
                        success = self.outreach_agent.send_outreach(candidate, product_details=details)
                        if success:
                            outreach_count += 1
                            logger.info(f"  ✅ Outreach sent to {candidate['name']}")
                            # Mark vendor status to avoid re-sending immediately?
                            # Usually OutreachAgent updates 'method' in requests.
                            # But we might want to update 'email_status' in vendors to 'Contacted'
                            # The db_manager.add_vendor sets it to 'Ready to Contact'.
                            # Ideally, OutreachAgent should handle this, or we do it here.
                            # For safety, let's assume we rely on manufacturer_requests checks in get_suppliers_for_outreach
                            pass
                        else:
                            logger.info(f"  ❌ Outreach failed for {candidate['name']}")
                            
                        time.sleep(random.uniform(5, 15))
                        
                    except Exception as e:
                        logger.error(f"  Outreach error: {e}")
            
            if outreach_count > 0:
                 self.db.update_sourcing_status(product_id, sent_inc=outreach_count)
            
            # Completion Check
            # If we are done effectively (no candidates OR enough sent), move on
            if not candidates or real_vendor_count >= MIN_SUPPLIERS:
                 # If we marked sourcing complete earlier, we can now mark outreach complete too
                 # This removes it from the 'get_products_for_sourcing' query which checks for 'pending'/'sourcing'
                 self.db.update_sourcing_status(product_id, status='outreach_complete')

            logger.info(f"Finished cycle for {product_name}. Sleeping...")
            time.sleep(2)

if __name__ == "__main__":
    coordinator = OutreachCoordinator()
    coordinator.run_pipeline()
