#!/usr/bin/env python3
"""
Test extraction on a proper RFQ (not admin notice) to validate improvements
"""
import sys
import os
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from run_email_campaign import format_service_email_body
import sqlite3

DB_PATH = "rebusiness_automation.db"

# Find a good RFQ to test
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT s.contract_id, s.title, COUNT(a.id) as att_count
    FROM solicitations s
    JOIN attachments a ON s.contract_id = a.contract_id
    WHERE s.title NOT LIKE '%NOTICE OF INTENT%'
      AND s.title NOT LIKE '%AWARD%'
      AND s.title NOT LIKE '%SOURCES SOUGHT%'
    GROUP BY s.contract_id
    HAVING COUNT(a.id) >= 2
    ORDER BY COUNT(a.id) DESC
    LIMIT 1
""")

row = cursor.fetchone()

if not row:
    print("No suitable RFQ found for testing")
    sys.exit(1)

contract_id, title, att_count = row

print("="*80)
print(f"Testing Extraction on Full RFQ")
print(f"Contract: {contract_id}")
print(f"Title: {title}")
print(f"Attachments: {att_count}")
print("="*80)

# Delete old analysis to force re-extraction
cursor.execute("DELETE FROM solicitation_analysis WHERE contract_id = ?", (contract_id,))
conn.commit()

# Run extraction
agent = AttachmentReaderAgent()
result = agent.create_summary_report(contract_id)

print("\n✅ Extraction Complete!")
print(f"\n📊 Key Fields Extracted:")
print(f"  - Soliciting Entity: {result.get('soliciting_entity', 'MISSING')}")
print(f"  - Contract Type: {result.get('contract_type', 'MISSING')}")
print(f"  - Set-Aside: {result.get('set_aside_type', 'MISSING')}")
print(f"  - Due Date: {result.get('quotes_due_date', 'MISSING')}")
print(f"  - Delivery Address: {result.get('delivery_requirements', {}).get('primary_destination_address', 'MISSING')}")
print(f"  - Product Details: {len(result.get('product_details', []))} items")
print(f"  - CLINs: {len(result.get('clins', []))} items")
print(f"  - Wage Requirements: {result.get('wage_labor_requirements', {})}")

# Generate email to test population
cursor.execute("""
    SELECT p.product_name, p.quantity, p.specifications, p.description
    FROM products p
    WHERE p.contract_id = ?
    LIMIT 1
""", (contract_id,))

product_row = cursor.fetchone()

if product_row:
    subject, plain, html = format_service_email_body(
        sol_id=contract_id,
        sol_title=title,
        product_name=product_row[0],
        quantity=product_row[1],
        specs=product_row[2],
        delivery_loc_json=None,
        timeline=None,
        description=product_row[3],
        due_date_str=None,
        sol_url=None,
        analysis_json=json.dumps(result)
    )
    
    fallback_count = plain.count("Information not provided in solicitation")
    print(f"\n📧 Email Fallback Count: {fallback_count}")
    
    if fallback_count < 5:
        print("✅ EXCELLENT - Low fallback count!")
    elif fallback_count < 10:
        print("⚠️  MODERATE - Some improvements needed")
    else:
        print("❌ HIGH - Extraction needs more work")
    
    print(f"\n{'='*80}")
    print("EMAIL PREVIEW (First 1000 chars)")
    print(f"{'='*80}")
    print(plain[:1000])

conn.close()
