#!/usr/bin/env python3
"""
Test RFQ Form Filling
Tests the form filler module with real vendor profiles
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_agents.ThomasNetAgent.form_filler import RFQFormFiller

def main():
    print("=" * 70)
    print("ThomasNet RFQ Form Filler Test")
    print("=" * 70)
    print()
    print("This test will:")
    print("  1. Open Firefox browser")
    print("  2. Navigate to ThomasNet")
    print("  3. Wait for you to log in manually")
    print("  4. Navigate to a vendor profile")
    print("  5. Fill out the RFQ form (without submitting)")
    print()
    input("Press Enter to start...")
    print()
    
    # Sample RFQ data
    rfq_data = {
        "summary": """Request for Quote: CNC Machining Services

We are seeking quotes for precision CNC machining services for aluminum parts.

Specifications:
- Material: 6061-T6 Aluminum
- Quantity: 100 units
- Tolerance: ±0.005"
- Finish: Anodized

Please provide:
1. Unit price for 100, 500, and 1000 quantities
2. Lead time
3. Quality certifications (ISO 9001, AS9100 if applicable)

Deadline: February 15, 2026""",
        "contact_info": {
            "name": "John Smith",
            "company": "Camp Sable Manufacturing",
            "email": "bobbysmitty078@gmail.com",
            "phone": "555-123-4567"
        }
    }
    
    with sync_playwright() as p:
        # Launch Firefox
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
        print("3. Navigate to ANY vendor profile page")
        print("   (Search for a product, click on a vendor)")
        print("4. Make sure you're on the vendor's profile page")
        print("5. Come back here and press Enter")
        print("=" * 70)
        print()
        input("Press Enter after you're on a vendor profile page...")
        print()
        
        # Get current URL
        current_url = page.url
        print(f"Current page: {current_url}")
        print()
        
        # Create vendor object from current page
        vendor = {
            "name": "Test Vendor",
            "profile_url": current_url
        }
        
        # Initialize form filler
        print("Initializing form filler...")
        form_filler = RFQFormFiller(page)
        
        print()
        print("=" * 70)
        print("Testing Form Filling (DRY RUN - NO SUBMISSION)")
        print("=" * 70)
        print()
        
        try:
            # Look for RFQ button/link
            print("Step 1: Looking for 'Request Quote' button...")
            
            # Common selectors for RFQ buttons on ThomasNet
            rfq_selectors = [
                'a:has-text("Request Quote")',
                'button:has-text("Request Quote")',
                'a:has-text("Get a Quote")',
                'button:has-text("Get a Quote")',
                'a:has-text("Contact Supplier")',
                '[data-testid="request-quote-button"]',
                '.request-quote-btn',
                '.contact-supplier-btn'
            ]
            
            rfq_button = None
            for selector in rfq_selectors:
                try:
                    if page.locator(selector).first.is_visible(timeout=2000):
                        rfq_button = page.locator(selector).first
                        print(f"✓ Found RFQ button with selector: {selector}")
                        break
                except:
                    continue
            
            if not rfq_button:
                print("❌ Could not find 'Request Quote' button on this page.")
                print("Please make sure you're on a vendor profile page.")
                print()
                print("Taking screenshot for debugging...")
                Path("logs").mkdir(exist_ok=True)
                page.screenshot(path="logs/vendor_profile_debug.png")
                print("Screenshot saved to: logs/vendor_profile_debug.png")
            else:
                print()
                print("Step 2: Clicking 'Request Quote' button...")
                rfq_button.click()
                time.sleep(2)
                
                print()
                print("Step 3: Filling out contact information...")
                
                # Try to fill contact fields
                contact_fields = {
                    "name": ['input[name="name"]', 'input[id*="name"]', 'input[placeholder*="Name"]'],
                    "company": ['input[name="company"]', 'input[id*="company"]', 'input[placeholder*="Company"]'],
                    "email": ['input[name="email"]', 'input[type="email"]', 'input[id*="email"]'],
                    "phone": ['input[name="phone"]', 'input[type="tel"]', 'input[id*="phone"]']
                }
                
                for field_name, selectors in contact_fields.items():
                    field_value = rfq_data["contact_info"].get(field_name, "")
                    filled = False
                    
                    for selector in selectors:
                        try:
                            field = page.locator(selector).first
                            if field.is_visible(timeout=1000):
                                field.fill(field_value)
                                print(f"  ✓ Filled {field_name}: {field_value}")
                                filled = True
                                break
                        except:
                            continue
                    
                    if not filled:
                        print(f"  ⚠️  Could not find field: {field_name}")
                
                print()
                print("Step 4: Filling out RFQ message/summary...")
                
                # Try to fill message/summary field
                message_selectors = [
                    'textarea[name="message"]',
                    'textarea[name="comments"]',
                    'textarea[name="description"]',
                    'textarea[id*="message"]',
                    'textarea[id*="comment"]',
                    'textarea[placeholder*="message"]',
                    'textarea'
                ]
                
                message_filled = False
                for selector in message_selectors:
                    try:
                        field = page.locator(selector).first
                        if field.is_visible(timeout=1000):
                            field.fill(rfq_data["summary"])
                            print(f"  ✓ Filled message field")
                            message_filled = True
                            break
                    except:
                        continue
                
                if not message_filled:
                    print("  ⚠️  Could not find message/summary field")
                
                print()
                print("=" * 70)
                print("Form Filling Complete!")
                print("=" * 70)
                print()
                print("✓ Contact information filled")
                print("✓ RFQ message filled")
                print()
                print("NOTE: This is a DRY RUN - the form was NOT submitted.")
                print("You can review the filled form in the browser.")
                print()
                
                # Take screenshot
                Path("logs").mkdir(exist_ok=True)
                screenshot_path = "logs/rfq_form_filled.png"
                page.screenshot(path=screenshot_path)
                print(f"Screenshot saved to: {screenshot_path}")
                print()
        
        except Exception as e:
            print(f"❌ Error during form filling: {e}")
            import traceback
            traceback.print_exc()
            
            # Save debug info
            Path("logs").mkdir(exist_ok=True)
            page.screenshot(path="logs/form_filler_error.png")
            with open("logs/form_filler_error.html", "w") as f:
                f.write(page.content())
            print("Debug files saved to logs/")
        
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
