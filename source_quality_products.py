#!/usr/bin/env python3
"""
Source suppliers for products that have complete solicitation data (with PDF attachments).
This ensures we only create outreach requests for solicitations with detailed information.
"""

import sys
import os
import logging
import subprocess
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from database_manager import DatabaseManager
from ai_agents.VendorValidatorAgent.vendor_validator import VendorValidatorAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("QualitySourcing")

db_manager = DatabaseManager()

def get_products_with_attachments(limit=None):
    """Get products from solicitations that have PDF attachments."""
    import sqlite3
    conn = sqlite3.connect("rebusiness_automation.db")
    cursor = conn.cursor()
    
    query = """
        SELECT DISTINCT
            p.id,
            p.product_name,
            p.contract_id,
            COUNT(a.id) as attachment_count
        FROM products p
        JOIN solicitations s ON p.contract_id = s.contract_id
        INNER JOIN attachments a ON s.contract_id = a.contract_id
        WHERE NOT EXISTS (
            SELECT 1 FROM product_suppliers ps WHERE ps.product_id = p.id
        )
        GROUP BY p.id
        HAVING attachment_count > 0
        ORDER BY attachment_count DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    return [{'id': r[0], 'product_name': r[1], 'contract_id': r[2], 'attachments': r[3]} for r in rows]

def source_suppliers_for_product(product):
    """Source suppliers for a single product using ThomasNet."""
    p_id = product['id']
    p_name = product['product_name']
    
    logger.info(f"📦 Sourcing: {p_name} (Contract: {product['contract_id']}, Attachments: {product['attachments']})")
    
    db_manager.update_sourcing_status(p_id, status='sourcing')
    
    try:
        # Call ThomasNet Agent
        cmd = [
            sys.executable,
            os.path.join('ai_agents', 'ThomasNetAgent', 'thomasnet_agent.py'),
            '--search', p_name,
            '--limit', '60'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        suppliers = []
        if result.returncode == 0:
            output = result.stdout.strip()
            import re
            match = re.search(r'\[.*\]', output, re.DOTALL)
            if match:
                try:
                    suppliers = json.loads(match.group(0))
                except: pass
        
        logger.info(f"  ✅ Found {len(suppliers)} potential suppliers")
        
        # Validate and link suppliers
        validator = VendorValidatorAgent()
        found_count = 0
        
        for s in suppliers:
            # Validate sector match
            is_match = validator.is_sector_match(
                s['name'],
                s.get('description', ''),
                p_name,
                ""
            )
            if not is_match:
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
        logger.info(f"  ✅ Linked {found_count} validated suppliers")
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Sourcing failed: {e}")
        db_manager.update_sourcing_status(p_id, status='sourcing_failed')
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Source suppliers for products with complete solicitation data')
    parser.add_argument('--limit', type=int, default=20, help='Number of products to process (default: 20)')
    args = parser.parse_args()
    
    logger.info("🔍 Quality Sourcing - Only Products with PDF Attachments")
    logger.info("=" * 80)
    
    products = get_products_with_attachments(limit=args.limit)
    
    if not products:
        logger.info("✅ No products need sourcing (all complete products already have suppliers)")
        return
    
    logger.info(f"Found {len(products)} products with complete data needing suppliers")
    
    success_count = 0
    for idx, product in enumerate(products, 1):
        logger.info(f"\n[{idx}/{len(products)}]")
        if source_suppliers_for_product(product):
            success_count += 1
        time.sleep(2)  # Rate limiting
    
    logger.info("\n" + "=" * 80)
    logger.info(f"✅ Sourcing Complete: {success_count}/{len(products)} successful")

if __name__ == "__main__":
    main()
