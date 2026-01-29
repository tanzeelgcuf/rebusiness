from playwright.sync_api import sync_playwright
import time

def run():
    print("Starting Playwright...")
    with sync_playwright() as p:
        print("Launching browser...")
        # Minimal args matching auth.py after fix
        browser = p.chromium.launch(headless=False)
        
        print("Creating context...")
        # Try with NO user agent first to see if that works
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        
        print("Creating page...")
        page = context.new_page()
        
        print("Navigating to Google (Control Test)...")
        try:
            page.goto("https://www.google.com")
            print("Google navigation successful")
        except Exception as e:
            print(f"Google navigation failed: {e}")
            
        print("Navigating to ThomasNet Login...")
        try:
            page.goto("https://www.thomasnet.com/thomas-auth/login")
            print("ThomasNet navigation successful")
            title = page.title()
            print(f"Page title: {title}")
        except Exception as e:
            print(f"ThomasNet navigation failed: {e}")
            
        browser.close()
    print("Done")

if __name__ == "__main__":
    run()
