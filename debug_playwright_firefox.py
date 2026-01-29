from playwright.sync_api import sync_playwright
import time

def run():
    print("Starting Playwright (Firefox)...")
    with sync_playwright() as p:
        print("Launching Firefox (headless=False)...")
        try:
            browser = p.firefox.launch(headless=False)
            context = browser.new_context(viewport={'width': 1280, 'height': 800})
            page = context.new_page()
            
            print("Navigating to ThomasNet Login...")
            page.goto("https://www.thomasnet.com/thomas-auth/login")
            print("ThomasNet navigation successful")
            print(f"Page title: {page.title()}")
            
            print("Waiting 10 seconds for you to see it...")
            time.sleep(10)
            
            browser.close()
            print("Done")
        except Exception as e:
            print(f"Firefox Failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    run()
