#!/usr/bin/env python3
"""
End-to-End Test: ThomasNet RFQ Submission Workflow
- Login to ThomasNet (manual)
- Search for vendors
- Select 5 vendors
- Fill out RFQ form
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_agents.ThomasNetAgent.auth import ThomasNetAuth
from ai_agents.ThomasNetAgent.searcher import ThomasNetSearch
from ai_agents.ThomasNetAgent.vendor_selector import VendorSelector
from ai_agents.ThomasNetAgent.form_filler import RFQFormFiller

def test_end_to_end_workflow():
    """Test complete RFQ submission workflow with manual login"""
    print("=" * 70)
    print("ThomasNet End-to-End RFQ Workflow Test")
    print("=" * 70)
    print()
    print("This test will:")
    print("  1. Open browser (WebKit/Safari-like)")
    print("  2. Navigate to ThomasNet login")
    print("  3. Wait for you to log in manually")
    print("  4. Search for vendors")
    print("  5. Select top 5 vendors")
    print("  6. Fill out RFQ form for each vendor")
    print()
    print("⚠️  You will need to:")
    print("   - Log in manually when browser opens")
    print("   - Solve any captchas")
    print()
    input("Press Enter to start...")
    print()
    
    # Test parameters
    search_query = "CNC machining services"
    rfq_data = {
        "product_name": "Custom CNC Parts",
        "quantity": "1000 units",
        "specifications": "Aluminum 6061, tolerance ±0.001 inches",
        "delivery_date": "60 days",
        "additional_notes": "Need ISO 9001 certified supplier"
    }
    
    auth = None
    try:
        # Step 1: Authentication
        print("Step 1: Opening browser and navigating to ThomasNet...")
        print("-" * 70)
        auth = ThomasNetAuth(headless=False)  # Non-headless for manual login
        page = auth.start_browser()
        
        print("✓ Browser opened")
        print()
        print("Step 2: Please log in manually...")
        print("-" * 70)
        print("⚠️  The browser window is now open.")
        print("⚠️  Please log in to ThomasNet manually.")
        print("⚠️  Solve any captchas if they appear.")
        print()
        input("Press Enter after you've logged in successfully...")
        print()
        
        # Validate that browser is still open
        try:
            print("Validating browser connection...")
            current_url = page.url
            print(f"✓ Browser is active. Current URL: {current_url}")
        except Exception as e:
            print(f"❌ Browser connection lost: {e}")
            print("The browser may have been closed. Please keep it open.")
            return
        
        # Step 2: Search for vendors
        print(f"Step 3: Searching for vendors: '{search_query}'...")
        print("-" * 70)
        searcher = ThomasNetSearch(page)
        vendors = searcher.search_vendors(search_query, max_results=20)
        
        if not vendors:
            print("❌ No vendors found. Test cannot continue.")
            return
        
        print(f"✓ Found {len(vendors)} vendors")
        print()
        
        # Step 3: Select top 5 vendors
        print("Step 4: Selecting top 5 vendors...")
        print("-" * 70)
        selector = VendorSelector()
        selected_vendors = selector.select_vendors(vendors, max_vendors=5)
        
        print(f"✓ Selected {len(selected_vendors)} vendors:")
        for i, vendor in enumerate(selected_vendors, 1):
            print(f"  {i}. {vendor.get('name', 'Unknown')}")
            print(f"     Score: {vendor.get('selection_score', 'N/A')}")
            print(f"     Rating: {vendor.get('rating', 'N/A')}")
        print()
        
        # Step 4: Fill out RFQ forms
        print("Step 5: Filling out RFQ forms...")
        print("-" * 70)
        form_filler = RFQFormFiller(page)
        
        successful_submissions = 0
        failed_submissions = 0
        
        for i, vendor in enumerate(selected_vendors, 1):
            vendor_name = vendor.get('name', 'Unknown')
            print(f"\n[{i}/{len(selected_vendors)}] Processing: {vendor_name}")
            print("  " + "-" * 66)
            
            try:
                # Navigate to vendor's RFQ page
                vendor_url = vendor.get('url') or vendor.get('profile_url')
                if not vendor_url:
                    print(f"  ⚠️  No URL found for {vendor_name}, skipping...")
                    failed_submissions += 1
                    continue
                
                print(f"  → Navigating to: {vendor_url}")
                page.goto(vendor_url, wait_until="domcontentloaded", timeout=30000)
                
                # Fill the form
                print(f"  → Filling RFQ form...")
                success = form_filler.fill_rfq_form(
                    product_name=rfq_data["product_name"],
                    quantity=rfq_data["quantity"],
                    specifications=rfq_data["specifications"],
                    delivery_date=rfq_data["delivery_date"],
                    additional_notes=rfq_data["additional_notes"]
                )
                
                if success:
                    print(f"  ✓ Successfully submitted RFQ to {vendor_name}")
                    successful_submissions += 1
                else:
                    print(f"  ❌ Failed to submit RFQ to {vendor_name}")
                    failed_submissions += 1
                    
            except Exception as e:
                print(f"  ❌ Error processing {vendor_name}: {e}")
                failed_submissions += 1
        
        # Summary
        print()
        print("=" * 70)
        print("Test Summary")
        print("=" * 70)
        print(f"Vendors found: {len(vendors)}")
        print(f"Vendors selected: {len(selected_vendors)}")
        print(f"Successful submissions: {successful_submissions}")
        print(f"Failed submissions: {failed_submissions}")
        print()
        
        if successful_submissions > 0:
            print("✅ Test completed with some successful submissions!")
        else:
            print("❌ Test completed but no successful submissions")
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if auth:
            print("\n🔒 Closing browser...")
            auth.close()
            print("✓ Browser closed")
    
    print()
    print("=" * 70)
    print("End-to-End test complete")
    print("=" * 70)

if __name__ == "__main__":
    test_end_to_end_workflow()
