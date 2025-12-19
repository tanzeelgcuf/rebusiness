from playwright.sync_api import sync_playwright
import time
import random

def scrape_bing_thomasnet(product_name):
    print(f"Searching Bing for ThomasNet listings of: {product_name}")
    query = f"site:thomasnet.com {product_name}"
    search_url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(search_url, timeout=30000)
            time.sleep(2) # Wait for results
            
            # Bing selectors (approximate, might need adjustment)
            # Usually results are in li.b_algo h2 a
            results = page.query_selector_all('li.b_algo h2 a')
            
            print(f"Found {len(results)} results on Bing.")
            
            for res in results:
                title = res.inner_text()
                href = res.get_attribute('href')
                print(f"  Title: {title}")
                print(f"  Link: {href}")
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    scrape_bing_thomasnet("Industrial Bolts")
