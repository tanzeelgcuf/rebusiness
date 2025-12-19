import sys
import os
import time
import json
import csv
import hashlib
import urllib.request
import urllib.error
from playwright.sync_api import sync_playwright

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import config

class SamGovAgent:
    def __init__(self):
        self.playwright = sync_playwright().start()
        # Use headless=True for production, can set False for debug
        self.browser = self.playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        self.page = self.context.new_page()
        self.search_url = "https://sam.gov/search/"
        self.checkpoint_file = "sam_gov_last_run.json"

    def ensure_solicitation_directory(self, contract_id):
        """Creates a directory for a specific solicitation."""
        base_dir = "data/solicitations"
        contract_dir = os.path.join(base_dir, contract_id)
        if not os.path.exists(contract_dir):
            os.makedirs(contract_dir)
        return contract_dir

    def _load_checkpoint(self):
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                try:
                    data = json.load(f)
                    return data.get('last_run_timestamp')
                except json.JSONDecodeError:
                    return None
        return None

    def _save_checkpoint(self):
        with open(self.checkpoint_file, 'w') as f:
            json.dump({'last_run_timestamp': time.time()}, f)

    def _download_file(self, url, target_dir):
        """Downloads a file using requests with Playwright cookies."""
        try:
            local_filename = url.split('/')[-1].split('?')[0] or "downloaded_file"
            if not local_filename or len(local_filename) > 100:
                local_filename = f"attachment_{int(time.time())}.dat"
            
            target_path = os.path.join(target_dir, local_filename)
            
            # Get cookies from Playwright context
            cookies = self.context.cookies()
            cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Cookie": cookie_header
            }

            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    if response.status == 200:
                        with open(target_path, 'wb') as f:
                            while True:
                                chunk = response.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                        print(f"    Downloaded: {local_filename}")
                        return local_filename
                    else:
                        print(f"    Failed to download {url}: Status {response.status}")
                        return None
            except urllib.error.URLError as e:
                 print(f"    Failed to download {url}: {e}")
                 return None

        except Exception as e:
            print(f"    Error downloading {url}: {e}")
            return None

    def search_for_new_solicitations(self, search_term):
        print("--- Searching for new solicitations (Playwright) ---")
        last_run_timestamp = self._load_checkpoint()
        
        start_date = None
        if last_run_timestamp:
            start_date = time.strftime('%m/%d/%Y', time.gmtime(last_run_timestamp))
            print(f"Searching for solicitations updated since {start_date}")

        solicitations = self.search_and_scrape(search_term, start_date)
        
        self._save_checkpoint()
        print("--- New solicitation search complete ---")
        return solicitations

    def search_and_scrape(self, search_term, start_date=None, max_pages=1):
        print(f"--- Starting SAM.gov Full Solicitation Search for: {search_term} (Limit: {max_pages} pages) ---")
        
        # Navigate
        try:
            self.page.goto(self.search_url, timeout=60000)
            self.page.wait_for_selector("#newSimpleSearch", timeout=60000)
            print("Search page loaded.")
            
            # Input Search
            self.page.fill("#newSimpleSearch", f'"{search_term}"')
            self.page.press("#newSimpleSearch", "Enter")
            
            # Wait for results
            self.page.wait_for_selector("app-opportunity-result", timeout=60000)
            print("Initial search results loaded.")
            
        except Exception as e:
            print(f"Error accessing search page: {e}")
            return []

        all_solicitations = []
        page_num = 1
        
        while page_num <= max_pages:
            print(f"Scraping page {page_num}...")
            
            # Get list of links on current page
            links = []
            try:
                results = self.page.query_selector_all("app-opportunity-result h3 a")
                for link in results:
                    href = link.get_attribute("href")
                    if href:
                        # Construct full URL if relative
                        if href.startswith('/'):
                            href = "https://sam.gov" + href
                        links.append(href)
            except Exception as e:
                print(f"Error extracting links: {e}")
            
            print(f"  Found {len(links)} links on this page.")
            
            # CRITICAL LOOP FIX: If no links found, STOP.
            if len(links) == 0:
                print("No results found on this page. Stopping search.")
                break
            
            # Process each link (Detail Visting)
            # Store current search URL to return to
            search_page_url = self.page.url 
            
            for url in links:
                try:
                    sol_data = self.process_detail_page(url)
                    if sol_data:
                        all_solicitations.append(sol_data)
                except Exception as e:
                    print(f"Error processing {url}: {e}")
                    # Try to recover context if page crashed?
                    pass

            # Pagination
            # Re-navigate to search page/next page context if we drifted, 
            # BUT since we visited links, we need to go back or ensure we are on the list.
            # Best pattern: Open details in new tabs? Or just navigate back.
            # Navigating back in SPA is tricky. 
            # Safer: Capture the "Next" button URL? No, it's a button.
            # Alternative: Re-run the search for Page N? 
            # Let's try `page.goto(search_page_url)` and then click next?
            # Or simpler: Store the URLs, process them, then come back.
            
            # "Coming back" to the exact pagination state in an SPA is hard.
            # STRATEGY: 
            # 1. Scrape all URLs from the current page.
            # 2. Visit them one by one.
            # 3. Use `page.go_back()`? 
            # Let's try strict `page.goto(search_page_url)`? No, that resets search.
            # Let's try `page.go_back()` matching the depth of visits.
            # Actually, `page.go_back()` works well in Playwright.
            
            # But wait, we are inside the loop. 
            # To fetch "Next Page", we must be on the Search Results page.
            # So after processing all links, we MUST be on Search Results page.
            
            # Since `process_detail_page` navigates away, we need to restore state.
            
            # OPTIMIZATION: Open details in a separate page (tab)!
            # This preserves the Search Results page state perfectly.
            
            # Check for Next Button
            try:
                # Ensure we are on search page (we haven't left it IF we used tabs, see below)
                next_btn = self.page.query_selector("//button[contains(text(), 'Next')]")
                if next_btn and not next_btn.is_disabled():
                    next_btn.click()
                    self.page.wait_for_load_state("networkidle")
                    # Wait for results to refresh (check for a spinner or stale element?)
                    # Simple wait for now
                    time.sleep(3) 
                    page_num += 1
                else:
                    print("Reached last page.")
                    break
            except Exception as e:
                print(f"Pagination error: {e}")
                break

        return list({v['url']:v for v in all_solicitations}.values())

    def process_detail_page(self, url):
        """
        Opens a new page to scrape the detail, preventing disruption of the main search flow.
        """
        detail_page = self.context.new_page()
        sol_data = None
        try:
            print(f"  Visiting {url}...")
            detail_page.goto(url, timeout=45000)
            # detail_page.wait_for_load_state("domcontentloaded") # Faster than networkidle
            detail_page.wait_for_selector("h1", timeout=30000)
            
            title = detail_page.locator("h1").first.text_content().strip()
            page_text = detail_page.locator("body").inner_text()
            
            # ID Extraction
            contract_id = hashlib.md5(url.encode()).hexdigest()[:10]
            try:
                # Assuming element ID 'grand-notice-id' exists
                nid = detail_page.query_selector("#grand-notice-id")
                if nid:
                    contract_id = nid.inner_text().strip().replace(" ", "_")
            except: pass
            
            # Files & Directory
            contract_dir = self.ensure_solicitation_directory(contract_id)
            
            # Description
            with open(os.path.join(contract_dir, "description.txt"), "w") as f:
                f.write(page_text)
                
            # Attachments
            # Extract hrefs
            attachment_dir = os.path.join(contract_dir, "attachments")
            if not os.path.exists(attachment_dir): os.makedirs(attachment_dir)
            
            file_exts = ['.pdf', '.docx', '.xlsx', '.xls', '.doc', '.zip']
            links = detail_page.query_selector_all("a[href]")
            for link in links:
                href = link.get_attribute("href")
                if href and any(href.lower().endswith(ext) for ext in file_exts):
                     self._download_file(href, attachment_dir)
            
            # Inner Link Crawling
            linked_pages_dir = os.path.join(contract_dir, "linked_pages")
            if not os.path.exists(linked_pages_dir): os.makedirs(linked_pages_dir)
            
            import re
            urls_in_text = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', page_text)
            unique_urls = set(urls_in_text)
            visited_count = 0
            for inner_url in unique_urls:
                if visited_count >= 10: break
                if url in inner_url or "google" in inner_url or "facebook" in inner_url: continue
                
                try:
                    # Use requests for speed on inner links
                    r = requests.get(inner_url, timeout=10, stream=True)
                    
                    # CHECK 1: Is the link itself a PDF?
                    content_type = r.headers.get('Content-Type', '').lower()
                    if 'application/pdf' in content_type or inner_url.lower().endswith('.pdf'):
                        print(f"    Found Level 2 PDF: {inner_url}")
                        self._download_file(inner_url, attachment_dir)
                        visited_count += 1
                        continue

                    # CHECK 2: It's a web page, scrape text AND look for nested PDFs
                    if r.status_code == 200:
                        safe_name = hashlib.md5(inner_url.encode()).hexdigest() + ".txt"
                        text_content = r.text
                        
                        # Save Page Text
                        with open(os.path.join(linked_pages_dir, safe_name), "w") as f:
                            f.write(f"Source: {inner_url}\n\n{text_content[:100000]}")
                        
                        # Level 2 PDF Extraction (Simple Regex)
                        pdf_links = re.findall(r'href=[\'"]?([^\'" >]+\.pdf)', text_content, re.IGNORECASE)
                        for pdf_link in pdf_links:
                            if not pdf_link.startswith('http'):
                                # Try to resolve relative link (imperfect but better than nothing)
                                from urllib.parse import urljoin
                                pdf_link = urljoin(inner_url, pdf_link)
                            
                            print(f"      Found Nested PDF: {pdf_link}")
                            self._download_file(pdf_link, attachment_dir)

                        visited_count += 1
                except Exception as e: 
                    print(f"    Error scraping inner link {inner_url}: {e}")

            # Metadata
            with open(os.path.join(contract_dir, "metadata.json"), "w") as f:
                json.dump({"url": url, "title": title, "contract_id": contract_id}, f)

            sol_data = {
                'title': title,
                'url': url,
                'description': page_text[:3000],
                'contract_id': contract_id
            }
            
        except Exception as e:
            print(f"Error on detail page {url}: {e}")
        finally:
            detail_page.close() # CRITICAL: Close the tab!
            
        return sol_data

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

if __name__ == "__main__":
    from database_manager import DatabaseManager
    
    print("--- Starting SamGovAgent Scraper (Playwright) ---")
    agent = SamGovAgent()
    db = DatabaseManager()
    
    try:
        term = "manufacturing products"
        combined_solicitations = agent.search_for_new_solicitations(term)
            
        print(f"\n--- Saving {len(combined_solicitations)} solicitations to Database ---")
        for sol in combined_solicitations:
            db.add_solicitation(
                contract_id=sol['contract_id'],
                url=sol['url'],
                title=sol['title'],
                description=sol['description'],
                location="USA",
                product_requirements=None,
                analysis_summary=None,
                data="{}"
            )
    except Exception as e:
        print(f"CRITICAL ERROR in main loop: {e}")
    finally:
        agent.close()
        print("--- Scraper Finished ---")
