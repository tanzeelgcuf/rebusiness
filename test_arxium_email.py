#!/usr/bin/env python3
"""
Test email generation with a specific solicitation that has attachments
"""

import sqlite3
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from run_email_campaign import format_product_email_body, format_service_email_body

DB_PATH = "rebusiness_automation.db"

# Test with ARxIUM contract (has 4 attachments)
contract_id = "197aaa46ad6c461db627c6934ba7fea4"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT s.contract_id, s.title, s.analysis_summary, s.data, s.url,
           p.product_name, p.quantity, p.specifications, p.description
    FROM solicitations s
    JOIN products p ON s.contract_id = p.contract_id
    WHERE s.contract_id = ?
    LIMIT 1
""", (contract_id,))

row = cursor.fetchone()

if row:
    print("="*80)
    print(f"Testing: {row[1]}")
    print("="*80)
    
    # Check attachments
    cursor.execute("SELECT file_path FROM attachments WHERE contract_id = ?", (contract_id,))
    attachments = cursor.fetchall()
    print(f"\nAttachments ({len(attachments)}):")
    for att in attachments:
        print(f"  - {att[0].split('/')[-1]}")
    
    # Parse analysis to check what was extracted
    if row[2]:
        analysis = json.loads(row[2])
        print(f"\nExtracted Data Summary:")
        print(f"  - Soliciting Entity: {analysis.get('soliciting_entity', 'N/A')}")
        print(f"  - Contract Type: {analysis.get('contract_type', 'N/A')}")
        print(f"  - Set-Aside: {analysis.get('set_aside_type', 'N/A')}")
        print(f"  - NAICS: {analysis.get('naics_code', 'N/A')}")
        print(f"  - Due Date: {analysis.get('quotes_due_date', 'N/A')}")
        print(f"  - Product Details: {len(analysis.get('product_details', []))} items")
        print(f"  - CLINs: {len(analysis.get('clins', []))} items")
        print(f"  - Delivery Location: {analysis.get('delivery_requirements', {}).get('primary_destination_address', 'N/A')}")
        print(f"  - Wage Requirements: {analysis.get('wage_labor_requirements', {})}")
    
    # Generate email
    subject, plain, html = format_service_email_body(
        sol_id=row[0],
        sol_title=row[1],
        product_name=row[5],
        quantity=row[6],
        specs=row[7],
        delivery_loc_json=None,
        timeline=None,
        description=row[8],
        due_date_str=None,
        sol_url=row[4],
        analysis_json=row[2]
    )
    
    print("\n" + "="*80)
    print("GENERATED EMAIL")
    print("="*80)
    print(plain)
    print("\n" + "="*80)
    
    # Count fallbacks
    fallback_count = plain.count("Information not provided in solicitation")
    print(f"\nFallback Count: {fallback_count}")
    
    if fallback_count > 8:
        print("⚠️  HIGH - Extraction needs improvement")
    elif fallback_count > 4:
        print("⚠️  MODERATE - Some data missing")
    else:
        print("✅ GOOD - Most data extracted")
else:
    print("Contract not found")

conn.close()
