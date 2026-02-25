#!/usr/bin/env python3
"""
Diagnostic script to find the correct selector for the "Request Quote" button
after selecting vendors on ThomasNet.

This will help us identify the exact HTML structure of the bottom selection div.
"""

from playwright.sync_api import sync_playwright
import time

def diagnose_request_quote_button():
    with sync_playwright() as p:
        # Connect to running Chrome
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        
        print("="*80)
        print(" Bottom Selection Div - HTML Structure Diagnostic")
        print("="*80)
        print()
        
        # Wait a bit for the bottom div to fully render
        print("Waiting 5 seconds for bottom selection div to render...")
        time.sleep(5)
        
        # Try to find all buttons on the page
        print("\n1. Looking for all buttons with 'Request' in text:")
        print("-"*80)
        request_buttons = page.query_selector_all('button, a, [role="button"]')
        for i, btn in enumerate(request_buttons):
            try:
                text = btn.text_content()
                if text and ('request' in text.lower() or 'quote' in text.lower()):
                    print(f"   Button {i}: '{text.strip()}'")
                    print(f"      Tag: {btn.evaluate('el => el.tagName')}")
                    print(f"      Classes: {btn.get_attribute('class')}")
                    print(f"      data-ref: {btn.get_attribute('data-ref')}")
                    print(f"      Visible: {btn.is_visible()}")
                    print()
            except: pass
        
        # Look for the bottom div container
        print("\n2. Looking for bottom selection container:")
        print("-"*80)
        possible_containers = [
            'div[class*="selected"]',
            'div[class*="shortlist"]',
            'div[class*="contact"]',
            'div[class*="supplier"]',
            '[data-ref*="selected"]',
            'footer',
            'aside'
        ]
        
        for selector in possible_containers:
            try:
                containers = page.query_selector_all(selector)
                if containers:
                    for container in containers:
                        text = container.text_content()
                        if text and len(text) > 20:  # Has substantial content
                            if 'send' in text.lower() or 'request' in text.lower():
                                print(f"   Found container: {selector}")
                                print(f"      Text preview: {text[:100]}...")
                                print(f"      Classes: {container.get_attribute('class')}")
                                print()
            except: pass
        
        # Get full page HTML for manual inspection
        print("\n3. Saving full page HTML for manual inspection...")
        html = page.content()
        with open("thomasnet_bottom_div_debug.html", "w") as f:
            f.write(html)
        print("   Saved to: thomasnet_bottom_div_debug.html")
        
        # Take screenshot
        print("\n4. Taking screenshot...")
        page.screenshot(path="thomasnet_bottom_div_debug.png", full_page=True)
        print("   Saved to: thomasnet_bottom_div_debug.png")
        
        print()
        print("="*80)
        print(" Diagnostic Complete")
        print("="*80)
        print()
        print("Please check:")
        print("  1. thomasnet_bottom_div_debug.html - Full page HTML")
        print("  2. thomasnet_bottom_div_debug.png - Screenshot")
        print()

if __name__ == "__main__":
    diagnose_request_quote_button()
