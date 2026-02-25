import os
from playwright.sync_api import sync_playwright

def inspect_thomasnet():
    with sync_playwright() as p:
        print("Connecting to CDP...")
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        
        # Check active pages
        pages = context.pages
        thomas_page = None
        for page in pages:
            if "thomasnet.com" in page.url:
                thomas_page = page
                break
                
        if not thomas_page:
            thomas_page = pages[0]
            print("Navigating to ThomasNet...")
            thomas_page.goto("https://www.thomasnet.com/suppliers")
            thomas_page.wait_for_load_state("domcontentloaded")
            thomas_page.wait_for_timeout(3000)
        
        print(f"Current URL: {thomas_page.url}")
        
        # If not on a search page, do a search
        if "/suppliers" not in thomas_page.url:
            thomas_page.goto("https://www.thomasnet.com/suppliers")
            thomas_page.wait_for_timeout(3000)
            
        print("Taking screenshot...")
        thomas_page.screenshot(path="thomasnet_live.png", full_page=True)
        
        print("Saving HTML...")
        with open("thomasnet_live.html", "w", encoding="utf-8") as f:
            f.write(thomas_page.content())
            
        print("Done. Saved to thomasnet_live.png and thomasnet_live.html")

if __name__ == "__main__":
    inspect_thomasnet()
