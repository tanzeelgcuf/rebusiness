import sys
from playwright.sync_api import sync_playwright

def run():
    print("Starting Playwright barebones test...")
    with sync_playwright() as p:
        # Use IPRoyal credentials directly
        proxy = {
            "server": "http://geo.iproyal.com:12321",
            "username": "tBhjRJVrJlpMGchF",
            "password": "uxUpaVJQ179XRuCk"
        }
        
        print(f"Launching browser with proxy server: {proxy['server']}...")
        browser = p.chromium.launch(headless=True, proxy=proxy)
        print("Browser launched.")
        
        context = browser.new_context()
        print("Context created.")
        
        page = context.new_page()
        print("Page created.")
        
        print("Navigating to icanhazip.com...")
        try:
            page.goto("https://ipv4.icanhazip.com", timeout=60000)
            print(f"IP: {page.text_content('body').strip()}")
        except Exception as e:
            print(f"Navigation failed: {e}")
            
        browser.close()

if __name__ == "__main__":
    run()
