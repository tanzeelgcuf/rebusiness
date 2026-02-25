#!/usr/bin/env python3
r"""
Test ThomasNet automation with the latest RFQ file from rfq_downloads folder.

This script automatically finds the most recent RFQ .docx file and uses it for testing.

Prerequisites:
1. Chrome running with remote debugging:
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"
2. You must be logged in to ThomasNet in that Chrome instance
"""

from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent
import os
import glob
from datetime import datetime

def find_latest_rfq_file(base_dir="rfq_downloads"):
    """
    Find the most recent RFQ .docx file in the rfq_downloads folder structure.
    
    Returns:
        str: Path to the latest RFQ file, or None if not found
    """
    # Get all date folders
    date_folders = glob.glob(os.path.join(base_dir, "2*"))
    
    if not date_folders:
        print(f"❌ No date folders found in {base_dir}")
        return None
    
    # Sort by folder name (date) to get most recent
    date_folders.sort(reverse=True)
    
    # Search for .docx files in recent folders
    for folder in date_folders:
        docx_files = glob.glob(os.path.join(folder, "*_RFQ_PRODUCT.docx"))
        
        if docx_files:
            # Get the most recently modified file in this folder
            latest_file = max(docx_files, key=os.path.getmtime)
            return latest_file
    
    print(f"❌ No RFQ .docx files found in {base_dir}")
    return None

if __name__ == "__main__":
    print("="*80)
    print(" ThomasNet RFQ Automation Test - Auto-Find Latest RFQ")
    print("="*80)
    print()
    
    # Find latest RFQ file
    print("Searching for latest RFQ file...")
    rfq_file = find_latest_rfq_file()
    
    if not rfq_file:
        print("\n❌ No RFQ file found. Please generate an RFQ first using the sam.gov agent.")
        exit(1)
    
    print(f"✅ Found RFQ file: {rfq_file}")
    
    # Get file info
    file_size = os.path.getsize(rfq_file)
    file_modified = datetime.fromtimestamp(os.path.getmtime(rfq_file))
    
    print(f"   Size: {file_size:,} bytes")
    print(f"   Modified: {file_modified.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("-"*80)
    print()
    
    # Test product (customize based on your needs)
    test_product = {
        'product_name': 'industrial bolts',
        'quantity': '1000 units',
        'due_date': 'March 15, 2026'
    }
    
    # Initialize agent
    agent = ThomasNetAgent()
    
    # Run workflow with attachment
    print(f"Starting RFQ workflow for: {test_product['product_name']}")
    print(f"Attachment: {os.path.basename(rfq_file)}")
    print()
    
    result = agent.select_vendors_and_submit_rfq(
        product=test_product,
        limit=5,
        attachment_file_path=rfq_file
    )
    
    print()
    print("="*80)
    print(" Test Result")
    print("="*80)
    
    if result.get('success'):
        print("✅ SUCCESS!")
        print(f"   Vendors contacted: {result.get('vendors_contacted', 'Unknown')}")
        print(f"   Attachment sent: {os.path.basename(rfq_file)}")
    elif result.get('error'):
        print(f"⚠️  ERROR: {result['error']}")
        print("   Please check the browser window for more details")
    else:
        print("❓ Unknown result")
    
    print()
