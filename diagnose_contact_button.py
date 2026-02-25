#!/usr/bin/env python3
"""
Diagnostic: Capture page state after selecting vendors
"""
import sys
import os
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from playwright.sync_api import sync_playwright

def diagnose_contact_button():
    """Captures the page after selecting vendors to debug button detection"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.new_page()
        
        # Navigate
        print("Navigating to ThomasNet...")
        term = 'Industrial+Bolts'
        url = f"https://www.thomasnet.com/suppliers/search?searchterm={term}&search_type=search-supplier"
        page.goto(url, timeout=60000)
        
        print("\nPlease solve CAPTCHA if needed, then wait...")
        time.sleep(30)  # Give user time to solve CAPTCHA
        
        # Select vendors
        print("\nSelecting 5 vendors...")
        checkboxes = page.query_selector_all('input[type="checkbox"]')
        print(f"Found {len(checkboxes)} checkboxes")
        
        selected = 0
        for checkbox in checkboxes[:5]:
            try:
                if checkbox.is_visible() and checkbox.is_enabled():
                    checkbox.click()
                    selected += 1
                    print(f"  Selected vendor {selected}")
                    time.sleep(0.5)
            except: pass
        
        print(f"\nSelected {selected} vendors. Now capturing page state...")
        time.sleep(2)
        
        # Capture page
        page.screenshot(path="debug_after_selection.png")
        with open("debug_after_selection.html", "w") as f:
            f.write(page.content())
        
        print("\nSaved:")
        print("  - debug_after_selection.png")
        print("  - debug_after_selection.html")
        
        # Try to find buttons
        print("\n=== Button Detection Test ===")
        all_buttons = page.query_selector_all('button')
        print(f"Total buttons on page: {len(all_buttons)}")
        
        for i, btn in enumerate(all_buttons):
            try:
                if btn.is_visible():
                    text = btn.text_content() or ""
                    aria = btn.get_attribute('aria-label') or ""
                    data_testid = btn.get_attribute('data-testid') or ""
                    if text or aria or data_testid:
                        print(f"\nButton {i}:")
                        if text: print(f"  Text: {text[:50]}")
                        if aria: print(f"  Aria: {aria[:50]}")
                        if data_testid: print(f"  TestID: {data_testid}")
            except: pass
        
        print("\nKeeping browser open for 10s for manual inspection...")
        time.sleep(10)
        browser.close()

if __name__ == "__main__":
    diagnose_contact_button()
