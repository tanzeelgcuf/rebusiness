#!/usr/bin/env python3
r"""
Test the updated ThomasNet workflow with actual UI elements:
- Individual "Select" buttons on vendor cards
- Bottom selection div
- "Request Quote" button

Prerequisites:
1. Chrome must be running with remote debugging:
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"
2. You must be logged in to ThomasNet in that Chrome instance
"""

from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent

if __name__ == "__main__":
    print("="*80)
    print(" ThomasNet RFQ Automation Test - Updated Workflow")
    print("="*80)
    print()
    print("Testing with actual ThomasNet UI:")
    print("  ✓ Individual 'Select' buttons on vendor cards")
    print("  ✓ Bottom selection div showing selected vendors")
    print("  ✓ 'Request Quote' button in bottom div")
    print()
    print("-"*80)
    print()
    
    # Test product (as a dictionary, which is what the method expects)
    test_product = {
        'product_name': 'industrial bolts',
        'quantity': '1000 units',
        'due_date': 'March 15, 2026'
    }
    
    # Initialize agent
    agent = ThomasNetAgent()
    
    # Run workflow with correct parameter
    print(f"Starting RFQ workflow for: {test_product['product_name']}")
    print()
    
    # Pass the product dictionary directly (not as separate parameters)
    result = agent.select_vendors_and_submit_rfq(
        product=test_product,
        limit=5
    )
    
    print()
    print("="*80)
    print(" Test Result")
    print("="*80)
    
    if result.get('success'):
        print("✅ SUCCESS!")
        print(f"   Vendors contacted: {result.get('vendors_contacted', 'Unknown')}")
    elif result.get('error'):
        print(f"⚠️  ERROR: {result['error']}")
        print("   Please check the browser window for more details")
    else:
        print("❓ Unknown result")
    
    print()

