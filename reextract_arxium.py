#!/usr/bin/env python3
"""
Re-extract ARxIUM contract with improved prompt and test email generation
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent

contract_id = "197aaa46ad6c461db627c6934ba7fea4"

print("="*80)
print("RE-EXTRACTING WITH IMPROVED PROMPT")
print("="*80)

agent = AttachmentReaderAgent()
result = agent.create_summary_report(contract_id)

print("\n✅ Extraction Complete!")
print(f"\nKey Fields Extracted:")
print(f"  - Soliciting Entity: {result.get('soliciting_entity', 'MISSING')}")
print(f"  - Due Date: {result.get('quotes_due_date', 'MISSING')}")
print(f"  - Delivery Address: {result.get('delivery_requirements', {}).get('primary_destination_address', 'MISSING')}")
print(f"  - Wage Determination: {result.get('wage_labor_requirements', {}).get('wage_determination', 'MISSING')}")
print(f"  - Product Details: {len(result.get('product_details', []))} items")

print("\n" + "="*80)
print("Now run: python3 test_arxium_email.py")
print("="*80)
