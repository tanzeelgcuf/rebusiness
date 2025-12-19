
from playwright.sync_api import sync_playwright

def snapshot_thomasnet():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            viewport={'width': 1366, 'height': 768}
        )
        
        # Mask webdriver
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        try:
            url = "https://www.thomasnet.com/nsearch.html?cov=NA&what=Industrial+Bolts&heading=0&searchsource=suppliers"
            print(f"Navigating to {url}")
            page.goto(url, timeout=30000)
            
            # Wait a bit
            page.wait_for_timeout(5000)
            
            # Screenshot
            page.screenshot(path="thomasnet_debug.png", full_page=True)
            print("Screenshot saved to thomasnet_debug.png")
            
            # Save HTML
            with open("thomasnet_debug.html", "w") as f:
                f.write(page.content())
            print("HTML saved to thomasnet_debug.html")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    snapshot_thomasnet()
