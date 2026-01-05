import sys
import time
import json
import csv
import subprocess
import os
import asyncio
import logging

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from database_manager import DatabaseManager
from ai_agents.OutreachAgent.outreach_agent import OutreachAgent
from ai_agents.VendorValidatorAgent.vendor_validator import VendorValidatorAgent

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BatchSourcing")

db_manager = DatabaseManager()

def import_leads_from_csv(csv_path="leads.csv"):
    """
    Imports leads from CSV into the database:
    1. Ensures Solicitation exists.
    2. Ensures Product exists.
    3. Ensures Manufacturer (Lead) exists.
    4. Links Product -> Manufacturer.
    """
    if not os.path.exists(csv_path):
        logger.warning(f"CSV file {csv_path} not found. Skipping import.")
        return

    logger.info(f"Importing leads from {csv_path}...")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            try:
                # 1. Solicitation
                contract_id = row.get('Solicitation ID')
                url = row.get('SAM.gov Link')
                if not contract_id: continue

                if not db_manager.solicitation_exists(contract_id):
                    db_manager.add_solicitation(
                        contract_id=contract_id,
                        url=url,
                        title=f"Imported Solicitation {contract_id}",
                        description="Imported from leads.csv",
                        location="USA", 
                        data="{}",
                        product_requirements="Imported from CSV",
                        analysis_summary="{}"
                    )

                # 2. Product
                product_name = row.get('Product Keyword')
                if not product_name: continue
                
                # Check if product exists for this contract?
                # Simplified: Just add, DB handles IDs. 
                # Ideally we check duplication but 'add_product' doesn't seem to enforce unique name/contract constraint in code provided.
                # Use a lightweight check if possible, or just add.
                # For now, we add. If redundant, it adds multiple rows. 
                # (Ideally we'd select first).
                
                # Let's try to find existing product to avoid bloating DB
                existing_products = db_manager.get_products_by_contract(contract_id)
                product_id = None
                for p in existing_products:
                    if p['product_name'] == product_name:
                        product_id = p['id']
                        break
                
                if not product_id:
                    product_id = db_manager.add_product(
                        contract_id=contract_id,
                        product_name=product_name,
                        quantity=row.get('Quantity Needed'),
                        specifications=row.get('Exact Size/Specs'),
                        description=f"{row.get('Material Composition', '')}"
                    )

                # 3. Manufacturer (Lead)
                lead_name = row.get('Lead: Company Name')
                if not lead_name: continue

                man_id = db_manager.add_manufacturer(
                    name=lead_name,
                    email=row.get('Lead: Verified Email'),
                    website=row.get('Lead: Website'),
                    address=row.get('Lead: Location'),
                    certifications=row.get('Lead: Specialty')
                )
                
                # Deduplication Handling for Manufacturer
                if not man_id:
                    # Likely exists, fetch it
                    existing = db_manager.get_manufacturer_by_name(lead_name)
                    if existing:
                        man_id = existing['id']
                
                # 4. Link
                if product_id and man_id:
                    db_manager.link_product_supplier(product_id, man_id)
                    count += 1
            
            except Exception as e:
                logger.error(f"Error importing row: {e}")

    logger.info(f"Imported {count} lead links from CSV.")

def run_thomasnet_sourcing(limit=20):
    """
    Finds suppliers for products that have NO suppliers yet.
    """
    logger.info("--- Phase 2: ThomasNet Sourcing ---")
    
    # Custom query or just get_products_for_sourcing
    products = db_manager.get_products_for_sourcing(limit=limit)
    if not products:
        logger.info("No products pending sourcing.")
        return

    logger.info(f"Sourcing for {len(products)} products...")
    
    validator = VendorValidatorAgent()
    supplier_target_per_product = 40 # User requested about 40
    
    for p in products:
        p_id = p['id']
        p_name = p['product_name']
        logger.info(f"> Sourcing: {p_name}")
        
        db_manager.update_sourcing_status(p_id, status='sourcing')
        
        try:
            # Call Agent via Subprocess
            cmd = [
                sys.executable, 
                os.path.join('ai_agents', 'ThomasNetAgent', 'thomasnet_agent.py'),
                '--search', p_name,
                '--limit', str(supplier_target_per_product)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            suppliers = []
            if result.returncode == 0:
                # Robust JSON Extraction
                output = result.stdout.strip()
                # find last bracketed list
                import re
                match = re.search(r'\[.*\]', output, re.DOTALL)
                if match:
                    try:
                        suppliers = json.loads(match.group(0))
                    except: pass
            
            logger.info(f"  Found {len(suppliers)} suppliers.")
            
            found_count = 0
            for s in suppliers:
                # NEW: Validate Sector Match
                is_match = validator.is_sector_match(
                    s['name'], 
                    s.get('description', ''), 
                    p_name, 
                    "" # Solicitation title could be passed here if we joined it
                )
                if not is_match:
                    logger.warning(f"  Skipping {s['name']}: Sector mismatch (Filtered).")
                    continue

                m_id = db_manager.add_manufacturer(
                    name=s['name'],
                    website=s['website'],
                    email=s.get('email'),
                    phone=s.get('phone'),
                    address=s.get('location')
                )
                
                if not m_id:
                     m = db_manager.get_manufacturer_by_name(s['name'])
                     if m: m_id = m['id']

                if m_id:
                    db_manager.link_product_supplier(p_id, m_id)
                    found_count += 1
            
            db_manager.update_sourcing_status(p_id, status='sourcing_complete', found_inc=found_count)
            time.sleep(2) 
        except Exception as e:
             logger.error(f"Sourcing failed for {p_name}: {e}")

async def run_outreach_campaign(limit=50):
    """
    Phase 3: Send emails to linked manufacturers.
    """
    logger.info("--- Phase 3: Outreach Campaign ---")
    
    agent = OutreachAgent(db_manager)
    
    # Get pending outreach targets
    targets = agent.get_pending_outreach(limit=limit)
    logger.info(f"Found {len(targets)} manufacturers needing outreach.")
    
    for t in targets:
        logger.info(f"Outreaching to: {t['name']} (for {t['product_name']})")
        
        # Pass the product details explicitly so the email is specific
        success = await agent.send_outreach(t, product_details=t)
        
        if success:
            logger.info("  -> Success")
        else:
            logger.info("  -> Failed")
        
        # Sleep slightly to be polite/avoid rate limits
        await asyncio.sleep(2)

async def main():
    # 1. Import
    import_leads_from_csv()
    
    # 2. Source (Sync but called here)
    run_thomasnet_sourcing(limit=600) # Process queue
    
    # 3. Outreach (Async)
    await run_outreach_campaign(limit=50)

if __name__ == "__main__":
    asyncio.run(main())
