
import os
import sys
import re
import time
import random
from unittest.mock import MagicMock
# Shim html5lib to prevent hangs on import
sys.modules['html5lib'] = MagicMock()

from bs4 import BeautifulSoup
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database_manager import DatabaseManager
from config import GEMINI_API_KEY
from config import GEMINI_API_KEY

# Lazy load genai to prevent startup timeouts
# import google.generativeai as genai

class ThomasNetAgent:
    """
    Agent for finding wholesalers/manufacturers by directly searching Thomasnet.com.
    """
    
    def __init__(self):
        self.db = DatabaseManager()
        self.model = None
        if GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
            except Exception as e:
                print(f"Warning: Gemini import failed: {e}")
    
    def find_suppliers_for_product(self, product, limit=40):
        """
        Find suppliers for a specific product using Direct Playwright Search on Thomasnet.
        """
        product_name = product['product_name']
        print(f"\nSearching ThomasNet directly for: {product_name} (Target: {limit} suppliers)")
        
        suppliers = []
        
        # 1. Direct Search on Thomasnet
        try:
            with sync_playwright() as p:
                # Use PERSISTENT CONTEXT to save cookies/login state
                import uuid
                import tempfile
                
                # Create unique temp dir for this run
                user_data_dir = os.path.join(tempfile.gettempdir(), f"thomasnet_chrome_{uuid.uuid4()}")
                os.makedirs(user_data_dir, exist_ok=True)
                
                # Launch options
                browser_context = p.chromium.launch_persistent_context(
                    user_data_dir,
                    headless=False, # Headed for manual interaction if needed
                    args=['--disable-blink-features=AutomationControlled'],
                    viewport={'width': 1366, 'height': 768},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
                )
                
                page = browser_context.new_page() if not browser_context.pages else browser_context.pages[0]
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # Search via Suppliers Page (Interactive)
                print(f"  Navigating to Search Page: https://www.thomasnet.com/suppliers")
                page.goto("https://www.thomasnet.com/suppliers", timeout=60000, wait_until="networkidle")
                
                # Strict Wait for "Complete Load" (User Request)
                print("  Waiting for page to initialize fully...")
                page.wait_for_load_state("domcontentloaded")
                time.sleep(5) # Explicit buffer for visual rendering
                
                # Wait for Input
                print("  Typing search term...")
                
                # Dismiss Cookie Banner if present
                try:
                    if page.is_visible('#gdpr-btn-accept'):
                        print("  Dismissing Cookie Banner...")
                        page.click('#gdpr-btn-accept')
                        time.sleep(1)
                except: pass

                # Input Search
                search_input_selector = 'input[data-ref="srp.DiscoverBox.input"]'
                try:
                    page.wait_for_selector(search_input_selector, state='visible', timeout=10000)
                    page.click(search_input_selector)
                    page.fill(search_input_selector, product_name)
                    
                    # Click Search
                    print("  Clicking Search...")
                    search_btn_selector = 'button[aria-label="Search"]' 
                    
                    try:
                         with page.expect_navigation(timeout=10000):
                            page.click(search_btn_selector)
                    except:
                        print("  Search click timeout. Attempting Enter key...")
                        page.press(search_input_selector, "Enter")
                        page.wait_for_load_state("networkidle", timeout=15000)

                except Exception as e:
                    print(f"  Interactive search skipped/failed: {e}")
                    # Efficient Fallback
                    term = product_name.replace(' ', '+')
                    url = f"https://www.thomasnet.com/suppliers/search?searchterm={term}&search_type=search-supplier"
                    print(f"  Navigating directly to results: {url}")
                    page.goto(url, timeout=60000, wait_until="networkidle")
                
                # CHECK FOR CAPTCHA / BLOCK
                time.sleep(2) 
                if "Access blocked" in page.title() or "captcha" in page.content().lower():
                    print("  ⚠️  Access Blocked / CAPTCHA detected!")
                    print("  Please solve the CAPTCHA in the browser window. Waiting up to 120s...")
                    try:
                        page.wait_for_selector('li[data-sentry-component="SearchResultSupplier"]', timeout=120000)
                        print("  Success! Access restored.")
                    except:
                        print("  Timed out waiting for manual CAPTCHA solution.")
                
                # Loop for Pagination until limit is reached
                page_count = 1
                while len(suppliers) < limit:
                    # Wait for results
                    print(f"  Scraping Page {page_count}...")
                    try:
                        page.wait_for_selector('li[data-sentry-component="SearchResultSupplier"]', timeout=15000)
                        # Explicit wait for content to settle
                        time.sleep(3) 
                    except:
                        print(f"  No results found on this page. URL: {page.url}")
                        break

                    # Parse current page
                    html_content = page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    items = soup.select('li[data-sentry-component="SearchResultSupplier"]')
                    print(f"  Page yielded {len(items)} results.")
                    
                    for item in items:
                        if len(suppliers) >= limit: break
                        try:
                            # Try robust selector first, fallback to h2 a
                            name_el = item.select_one('[data-testid="supplier-name-link"]')
                            if not name_el:
                                name_el = item.select_one('h2 a')
                            
                            if not name_el: 
                                print("  Skipping item: No name element found.")
                                continue
                            
                            name = name_el.get_text(strip=True)
                            
                            # Extract links
                            website = None
                            # Try specific website button first
                            website_btn = item.select_one('a[data-sentry-component="SupplierWebsite"]')
                            if website_btn:
                                website = website_btn.get('href')
                            else:
                                # Fallback loop
                                links = item.select('a')
                                for link in links:
                                    href = link.get('href', '')
                                    if 'navigator.thomasnet.com' in href or 'location' in href: continue 
                                    if href.startswith('http') and 'thomasnet.com' not in href:
                                        website = href
                                        break
                            
                            # Fallback: Profile Link (ThomasNet profile often has the real link)
                            if not website:
                                profile_href = name_el.get('href')
                                if profile_href:
                                     website = f"https://www.thomasnet.com{profile_href}" if profile_href.startswith('/') else profile_href

                            if name: # Website is optional (can use ThomasNet profile for outreach if needed, or skip)
                                # Deduplicate
                                if not any(s['name'] == name for s in suppliers):
                                    suppliers.append({
                                        'name': name,
                                        'website': website,
                                        'email': None, # To be filled by OutreachAgent
                                        'phone': None, 
                                        'location': None # Could extract address from card
                                    })
                        except Exception as e:
                            print(f"Error parsing item: {e}")

                    print(f"  Total Suppliers Found: {len(suppliers)}")
                    
                    # Pagination logic
                    if len(suppliers) < limit:
                        next_btn = page.query_selector('a[aria-label="Next Page"]')
                        if next_btn and next_btn.is_visible():
                            print("  Navigating to Next Page...")
                            next_btn.click()
                            page.wait_for_load_state("networkidle", timeout=15000)
                            page_count += 1
                        else:
                            print("  No 'Next Page' button found. End of results.")
                            break
                    else:
                        break

                browser_context.close()
                try:
                    import shutil
                    shutil.rmtree(user_data_dir, ignore_errors=True)
                except: pass

        except Exception as e:
            print(f"Search failed: {e}")
            import traceback
            traceback.print_exc()
        
        return suppliers


    def parse_thomasnet_html(self, html_file_path):
        """
        Parses an HTML file from ThomasNet search results.
        """
        print(f"\nParsing ThomasNet HTML file: {html_file_path}")
        suppliers = []
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

            supplier_list_items = soup.select('li[data-sentry-component="SearchResultSupplier"]')

            if not supplier_list_items:
                supplier_list_items = soup.select('ul.search-list__list li')
                if not supplier_list_items:
                    supplier_list_items = soup.select('div.search-result-supplier ul li')

            print(f"Found {len(supplier_list_items)} items in list")

            for item in supplier_list_items:
                name_tag = item.select_one('[data-testid="supplier-name-link"]')
                if not name_tag:
                    name_tag = item.find('a', class_='supplier-name-link') 
                
                if name_tag:
                    company_name = name_tag.get_text(strip=True)
                    website_tag = item.select_one('a[data-sentry-component="SupplierWebsite"]')
                    website = website_tag.get('href') if website_tag else None
                    location_tag = item.select_one('[data-testid="srp.supplier-location-link"]')
                    location = location_tag.get_text(strip=True) if location_tag else None
                    description_tag = item.select_one('[data-sentry-component="TrimmedDescription"]')
                    description = description_tag.get_text(strip=True) if description_tag else None

                    print(f"  Found: {company_name} | Web: {website}")

                    if website and 'thomasnet.com' not in website:
                         suppliers.append({
                            'name': company_name,
                            'website': website,
                            'location': location,
                            'email': None, 
                            'phone': None, 
                            'source': 'ThomasNet HTML (Direct)',
                            'notes': f"Parsed from HTML. Location: {location}"
                        })
                    else:
                        supplier_info = self._enrich_supplier_details(company_name, "Parsed from ThomasNet HTML")
                        if supplier_info:
                            if location: supplier_info['location'] = location
                            suppliers.append(supplier_info)
                        else:
                            suppliers.append({
                                'name': company_name,
                                'website': None,
                                'location': location,
                                'email': None,
                                'phone': None,
                                'source': 'ThomasNet URL',
                                'notes': 'Parsed from ThomasNet URL'
                            })
        except Exception as e:
            print(f"Error parsing HTML file: {e}")
            
        return suppliers

    def _enrich_supplier_details(self, company_name, product_context):
        """
        Find company website and contact info.
        """
        print(f"  Enriching details for: {company_name}...")
        try:
            from duckduckgo_search import DDGS
            query = f"{company_name} official site contact email"
            results = DDGS().text(query, region='us-en', max_results=5)
            
            ignored_domains = [
                'youtube.com', 'facebook.com', 'linkedin.com', 'twitter.com', 
                'instagram.com', 'pinterest.com', 'thomasnet.com', 'zoominfo.com',
                'dnb.com', 'manta.com', 'bbb.org'
            ]
            
            best_match = None
            
            for res in results:
                href = res['href']
                domain = urlparse(href).netloc.lower()
                
                if any(ignored in domain for ignored in ignored_domains):
                    continue
                    
                best_match = res
                break
            
            if best_match:
                snippet = best_match['body']
                return {
                    'name': company_name,
                    'website': best_match['href'],
                    'email': self._extract_email(snippet),
                    'phone': self._extract_phone(snippet),
                    'source': 'ThomasNet via Search',
                    'notes': f"Identified as supplier for {product_context}"
                }
            else:
                print(f"  Could not find official site for {company_name}")
                
        except Exception as e:
            print(f"  Enrichment error for {company_name}: {e}")
            
        return None

    def _extract_email(self, text):
        # Stricter regex
        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        
        ignored_domains = [
            'example.com', 'w3.org', 'sentry.io', 'domain.com', 'email.com',
            'cloudflare.com', 'google.com', 'facebook.com', 'twitter.com',
            'linkedin.com', 'youtube.com', 'instagram.com', 'github.com',
            'wix.com', 'godaddy.com', 'wordpress.com'
        ]
        
        ignored_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css']
        
        valid_emails = []
        for e in emails:
            e_lower = e.lower()
            if any(ign in e_lower.split('@')[1] for ign in ignored_domains): continue
            if any(e_lower.endswith(ext) for ext in ignored_extensions): continue
            if len(e) < 6: continue 
            valid_emails.append(e)
            
        return valid_emails[0] if valid_emails else None

    def _extract_phone(self, text):
        match = re.search(r'(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', text)
        return match.group(0) if match else None

    def save_supplier(self, supplier):
        if not supplier: return
        self.db.add_manufacturer(
            name=supplier['name'],
            website=supplier['website'],
            email=supplier['email'],
            phone=supplier['phone']
        )

if __name__ == "__main__":
    import sys
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="ThomasNet Agent CLI")
    parser.add_argument("--search", type=str, help="Product name to search for")
    parser.add_argument("--limit", type=int, default=30, help="Number of suppliers to find")
    
    args = parser.parse_args()
    
    if args.search:
        # CLI Mode (used by main_workflow via subprocess)
        agent = ThomasNetAgent()
        try:
            suppliers = agent.find_suppliers_for_product({'product_name': args.search}, limit=args.limit)
            # Print ONLY JSON to stdout for capture
            print(json.dumps(suppliers))
        except Exception as e:
            # Print empty list on failure so parent doesn't crash
            print("[]")
            print(f"DEBUG: {e}", file=sys.stderr)
    else:
        # Test Mode
        agent = ThomasNetAgent()
        print("Running Test Search...")
        test_product = {'product_name': 'Industrial Bolts'}
        suppliers = agent.find_suppliers_for_product(test_product, limit=5)
        for s in suppliers:
            print(s)
