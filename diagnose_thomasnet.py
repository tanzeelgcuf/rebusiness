
import os
import time
import asyncio
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def diagnose():
    print("=== ThomasNet Diagnostic Tool ===")
    print("This script will open a browser. Please interact with it!")
    
    with sync_playwright() as p:
        # Launch Headful
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1366, 'height': 768})
        page = context.new_page()
        
        url = "https://www.thomasnet.com/suppliers/search?searchterm=Industrial+Bolts&search_type=search-supplier"
        print(f"1. Navigating to: {url}")
        
        try:
            page.goto(url, timeout=60000)
        except Exception as e:
            print(f"   Navigation hit an error (ignoring for debug): {e}")

        print("\n" + "!"*60)
        print("ACTION REQUIRED:")
        print("1. Please solve any CAPTCHA/Slider in the browser.")
        print("2. Scroll down to ensure vendor results are visible.")
        print("3. WHEN READY, press ENTER in this terminal.")
        print("!"*60 + "\n")
        
        print("   (Waiting 60 seconds - please act now!)")
        time.sleep(60) 
        # input("Press Enter to run diagnostics...")  # Disabled for automation safety
        
        print("\nRunning Diagnostics...")
        
        # 1. Take Screenshot
        page.screenshot(path="thomasnet_diagnostic.png")
        print("   -> Saved screenshot to 'thomasnet_diagnostic.png'")
        
        # 2. Save HTML
        content = page.content()
        with open("thomasnet_diagnostic.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("   -> Saved HTML to 'thomasnet_diagnostic.html'")
        
        # 3. Analyze Selectors
        soup = BeautifulSoup(content, 'html.parser')
        selectors = [
             'li[data-sentry-component="SearchResultSupplier"]',
             'div.search-result-supplier', 
             'div.supplier-card',
             'li.search-list__item',
             'div[data-testid="supplier-card"]',
             'h2 a'  # Fallback for just finding links
        ]
        
        print("\nSelector Check:")
        for sel in selectors:
            count = len(soup.select(sel))
            print(f"   [{sel}]: Found {count} items")
            
        print("\nDiagnostic Complete. You can close the browser.")
        time.sleep(5)
        browser.close()

if __name__ == "__main__":
    diagnose()
