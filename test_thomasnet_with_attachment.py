#!/usr/bin/env python3
r"""
Test the ThomasNet workflow with file attachment.

Prerequisites:
1. Chrome must be running with remote debugging:
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"
2. You must be logged in to ThomasNet in that Chrome instance
3. You must have an RFQ .docx file to attach (from the sam.gov agent)
"""

from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent
import sys

if __name__ == "__main__":
    print("="*80)
    print(" ThomasNet RFQ Automation Test - With File Attachment")
    print("="*80)
    print()
    
    # Check if attachment path is provided
    if len(sys.argv) < 2:
        print("Usage: python3 test_thomasnet_with_attachment.py <path_to_rfq_document.docx>")
        print()
        print("Example:")
        print("  python3 test_thomasnet_with_attachment.py /path/to/rfq_output.docx")
        print()
        sys.exit(1)
    
    attachment_path = sys.argv[1]
    print(f"Attachment file: {attachment_path}")
    print()
    print("-"*80)
    print()
    
    # Test product
    test_product = {
        'product_name': 'industrial bolts',
        'quantity': '1000 units',
        'due_date': 'March 15, 2026'
    }
    
    # Initialize agent
    agent = ThomasNetAgent()
    
    # Run workflow with attachment
    print(f"Starting RFQ workflow for: {test_product['product_name']}")
    print()
    
    result = agent.select_vendors_and_submit_rfq(
        product=test_product,
        limit=5,
        attachment_file_path=attachment_path
    )
    
    print()
    print("="*80)
    print(" Test Result")
    print("="*80)
    
    if result.get('success'):
        print("✅ SUCCESS!")
        print(f"   Vendors contacted: {result.get('vendors_contacted', 'Unknown')}")
        print(f"   Attachment: {attachment_path}")
    elif result.get('error'):
        print(f"⚠️  ERROR: {result['error']}")
        print("   Please check the browser window for more details")
    else:
        print("❓ Unknown result")
    
    print()
