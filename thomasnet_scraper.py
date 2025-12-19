import os
import sys
import time
import random
from playwright.sync_api import sync_playwright

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_manager import DatabaseManager
from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent

class ThomasNetScraper:
    def __init__(self, db_manager):
        self.db = db_manager
        self.agent = ThomasNetAgent()
        self.base_url = "https://www.thomasnet.com"

    def get_products_to_process(self, limit=5):
        """
        Fetch products from the database that need supplier discovery 
        using the new product_sourcing_status table.
        """
        return self.db.get_products_for_sourcing(limit=limit)

    def scrape_suppliers(self, product_id, product_name):
        """
        Scrape ThomasNet for a given product name using Playwright.
        """
        print(f"Searching ThomasNet for: {product_name} (ID: {product_id})")
        
        # Update status to sourcing
        self.db.update_sourcing_status(product_id, status='sourcing')

        term = product_name.replace(' ', '+')
        search_url = f"{self.base_url}/suppliers/search?cov=NA&searchsource=suppliers&searchterm={term}&searchx=true"
        
        suppliers_found_count = 0

        with sync_playwright() as p:
            # Launch in HEADED mode to look like a real user
            browser = p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                viewport={'width': 1366, 'height': 768},
                locale='en-US',
                timezone_id='America/New_York'
            )
            page = context.new_page()
            
            # Mask webdriver property
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            try:
                # Random delay before request to behave more human-like
                time.sleep(random.uniform(2, 5))
                
                print(f"  Navigating to: {search_url}")
                page.goto(search_url, timeout=60000)
                
                # Manual Login Handling (First time run check logic could be added here)
                # Check if we are redirected to login or captcha
                if "login" in page.url or "captcha" in page.content().lower():
                    print("  ⚠️  Login/Captcha detected! Please handle manually in the browser window.")
                    print("  Waiting 60 seconds for user intervention...")
                    time.sleep(60)
                
                # Wait for results
                try:
                    page.wait_for_selector('li[data-sentry-component="SearchResultSupplier"]', timeout=10000)
                except:
                    print("  No supplier list found or timeout waiting for selector.")
                
                # Scroll
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                time.sleep(1)

                # Get HTML content
                html_content = page.content()
                
                # Save to temporary file
                safe_name = "".join(c for c in product_name if c.isalnum() or c in (' ', '_')).rstrip()
                temp_file = f"temp_{safe_name.replace(' ', '_')}.html"
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                    
                print(f"  Saved HTML to {temp_file}")
                
                # Parse
                suppliers = self.agent.parse_thomasnet_html(temp_file)
                print(f"  Found {len(suppliers)} suppliers.")
                
                for s in suppliers:
                    # Save supplier
                    # Enrich notes with specific product
                    s['notes'] = f"{s.get('notes', '')} | ProductID: {product_id}"
                    
                    manufacturer_id = self.agent.save_supplier(s)
                    
                    if manufacturer_id:
                        # LINK supplier to product
                        if self.db.link_product_supplier(product_id, manufacturer_id):
                            suppliers_found_count += 1
                        
                # Cleanup
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
            except Exception as e:
                print(f"  Error scraping {product_name}: {e}")
            finally:
                browser.close()

        # Update final status
        self.db.update_sourcing_status(
            product_id, 
            status='sourcing_complete', 
            found_inc=suppliers_found_count
        )
        print(f"  Finished sourcing for {product_name}. Found {suppliers_found_count} new links.")

    def run(self, limit=5):
        products = self.get_products_to_process(limit)
        print(f"Found {len(products)} products needing sourcing.")
        
        for product in products:
            self.scrape_suppliers(product['id'], product['product_name'])
            # Random delay
            time.sleep(random.uniform(5, 10))

if __name__ == "__main__":
    db_manager = DatabaseManager()
    scraper = ThomasNetScraper(db_manager)
    
    # Process products
    scraper.run(limit=5)
