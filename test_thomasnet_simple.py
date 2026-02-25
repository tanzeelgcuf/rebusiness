#!/usr/bin/env python3
"""
Simplified End-to-End Test: ThomasNet RFQ Workflow
Keeps browser open throughout entire process
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_agents.ThomasNetAgent.vendor_selector import VendorSelector

def main():
    print("=" * 70)
    print("ThomasNet End-to-End Workflow Test (Simplified)")
    print("=" * 70)
    print()
    print("This test will:")
    print("  1. Open Firefox browser")
    print("  2. Navigate to ThomasNet")
    print("  3. Wait for you to log in and search manually")
    print("  4. Parse the search results")
    print("  5. Select top 5 vendors")
    print()
    input("Press Enter to start...")
    print()
    
    with sync_playwright() as p:
        # Launch Firefox in non-headless mode
        print("Opening Firefox browser...")
        browser = p.firefox.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.new_page()
        
        # Navigate to ThomasNet
        print("Navigating to ThomasNet...")
        page.goto("https://www.thomasnet.com")
        
        print()
        print("=" * 70)
        print("MANUAL STEPS:")
        print("=" * 70)
        print("1. Log in to ThomasNet in the browser window")
        print("2. Solve any captchas")
        print("3. Search for: 'CNC machining services'")
        print("4. Wait for search results to load")
        print("5. Come back here and press Enter")
        print("=" * 70)
        print()
        input("Press Enter after you've completed the search...")
        print()
        
        # Parse the current page (should be search results)
        print("Parsing search results from current page...")
        print("-" * 70)
        
        vendors = []
        try:
            # Wait a moment for page to settle
            time.sleep(2)
            
            # Try to find vendor cards
            # Using the selector from thomasnet_agent.py
            vendor_cards = page.locator('li[data-sentry-component="SearchResultSupplier"]').all()
            
            if not vendor_cards:
                print("⚠️  No vendor cards found with primary selector.")
                print("Trying alternative selectors...")
                vendor_cards = page.locator('div.supplier-card, div.profile-card').all()
            
            if not vendor_cards:
                print("❌ Could not find any vendor cards on the page.")
                print(f"Current URL: {page.url}")
                # Save debug info
                Path("logs").mkdir(exist_ok=True)
                page.screenshot(path="logs/search_results_debug.png")
                with open("logs/search_results_debug.html", "w") as f:
                    f.write(page.content())
                print("Saved debug files to logs/")
            else:
                print(f"✓ Found {len(vendor_cards)} vendor cards")
                print()
                
                # Parse each vendor card
                for idx, card in enumerate(vendor_cards[:20]):  # Limit to 20
                    try:
                        # Get vendor name
                        name_el = card.locator('[data-testid="supplier-name-link"]').first
                        if not name_el.is_visible():
                            name_el = card.locator('h2 a, h3 a').first
                        
                        name = name_el.inner_text().strip() if name_el.is_visible() else f"Vendor {idx+1}"
                        
                        # Get profile URL
                        profile_url = ""
                        if name_el.is_visible():
                            href = name_el.get_attribute("href")
                            if href:
                                profile_url = f"https://www.thomasnet.com{href}" if href.startswith("/") else href
                        
                        # Get location
                        loc_el = card.locator('[data-testid="srp.supplier-location-link"]').first
                        location = loc_el.inner_text().strip() if loc_el.is_visible() else "Unknown"
                        
                        # Check if verified
                        verified = card.locator('.verified, .registered, .certified').count() > 0
                        
                        vendor = {
                            "rank": idx + 1,
                            "name": name,
                            "profile_url": profile_url,
                            "location": location,
                            "verified": verified,
                            "rating": 0.0  # Default rating
                        }
                        
                        vendors.append(vendor)
                        print(f"  {idx+1}. {name} ({location})")
                        
                    except Exception as e:
                        print(f"  ⚠️  Error parsing vendor {idx+1}: {e}")
                        continue
        
        except Exception as e:
            print(f"❌ Error parsing results: {e}")
            import traceback
            traceback.print_exc()
        
        if vendors:
            print()
            print("=" * 70)
            print("Vendor Selection")
            print("=" * 70)
            
            # Use vendor selector to pick top 5
            selector = VendorSelector()
            selected = selector.select_top_vendors(vendors, product_data={"product_name": "CNC machining services"})
            
            print(f"✓ Selected {len(selected)} vendors:")
            print()
            for i, vendor in enumerate(selected, 1):
                print(f"{i}. {vendor['name']}")
                print(f"   Location: {vendor['location']}")
                print(f"   Verified: {vendor['verified']}")
                print(f"   Score: {vendor.get('selection_score', 'N/A')}")
                if vendor.get('profile_url'):
                    print(f"   URL: {vendor['profile_url']}")
                print()
            
            print("=" * 70)
            print("Next Steps:")
            print("=" * 70)
            print("You can now:")
            print("1. Visit each vendor's profile URL")
            print("2. Fill out RFQ forms manually")
            print("3. Or use the form_filler module to automate")
            print()
        else:
            print()
            print("❌ No vendors found to select from.")
        
        print()
        input("Press Enter to close browser...")
        
        browser.close()
        print("✓ Browser closed")
        print()
        print("=" * 70)
        print("Test Complete")
        print("=" * 70)

if __name__ == "__main__":
    main()
