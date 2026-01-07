import sys
import os
import time
import json
import csv
import hashlib
from datetime import datetime
import urllib.request
import urllib.error
from urllib.parse import urljoin
import zipfile
import re
import logging
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from database_manager import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import config


class SamGovAgent:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.visited_links = set()

        
        # User agents for rotation (helps bypass some restrictions)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        self.search_url = "https://sam.gov/search/"
        self.checkpoint_file = "sam_gov_last_run.json"

    def start_browser(self):
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
        contract_dir = os.path.join(config.SOLICITATION_DATA_DIR, contract_id)
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




    def _deep_download_attachments(self, page, target_dir):
        """
        Robustly downloads attachments using Playwright interactions.
        Prioritizes 'Download All' button, then individual links.
        Handles formatting and Terms of Service modals.
        """
        print(f"    [Deep Fetch] Starting attachment download to {target_dir}")

        # Check for Terms of Service Modal
        try:
            tos_accept = page.query_selector("button:has-text('Accept')")
            if tos_accept and tos_accept.is_visible():
                print("    [Deep Fetch] Found Terms of Service modal. Clicking Accept...")
                tos_accept.click()
                time.sleep(2)
        except: pass

        # Ensure the Attachments/Links section is visible (dynamic content)
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            header = page.query_selector("h2:has-text('Attachments/Links'), h3:has-text('Attachments/Links')")
            if header:
                header.scroll_into_view_if_needed()
                time.sleep(1)
        except: pass

        download_count = 0
        
        # Priority 1: Download All Button
        try:
            # Look for button with text "Download All"
            download_all_btn = page.query_selector("button:has-text('Download All')")
            if not download_all_btn:
                # Try specific selector often found in SAM
                download_all_btn = page.query_selector("#files button")
            
            # Verify text content just in case selector matched something else
            if download_all_btn:
                txt = download_all_btn.inner_text() or ""
                if "Download All" in txt:
                    print("    [Deep Fetch] Found 'Download All' button. Clicking...")
                    try:
                        with page.expect_download(timeout=30000) as download_info:
                            download_all_btn.click()
                        download = download_info.value
                        
                        # Generate safe name
                        safe_name = f"bundle_{int(time.time())}.zip"
                        save_path = os.path.join(target_dir, safe_name)
                        download.save_as(save_path)
                        print(f"    [Deep Fetch] Downloaded Bundle: {safe_name}")
                        download_count += 1
                        
                        # Unzip immediately
                        try:
                            with zipfile.ZipFile(save_path, 'r') as zip_ref:
                                zip_ref.extractall(target_dir)
                            print("    [Deep Fetch] Unzipped bundle.")
                        except Exception as e:
                            print(f"    [Deep Fetch] Failed to unzip: {e}")
                            
                    except Exception as e:
                        print(f"    [Deep Fetch] Failed to complete 'Download All': {e}")
        except Exception as e:
            print(f"    [Deep Fetch] Error checking 'Download All': {e}")

        # Priority 2: Individual Files (Scavenge)
        # Scan for anything that looks like a file link/button
        try:
            # Look for anchors and buttons
            elements = page.query_selector_all("a, button, div[role='button']")
            for el in elements:
                try:
                    if not el.is_visible(): continue
                    text = el.inner_text() or ""
                    href = el.get_attribute("href") or ""
                    
                    is_file = False
                    # Check extensions in text or href
                    if any(ext in text.lower() for ext in ['.pdf', '.docx', '.xlsx', 'statement of work', 'sow', 'specs']):
                        is_file = True
                    if "/api/prod/" in href:
                         is_file = True
                    
                    # Avoid downloading the bundle again or navigational links
                    if is_file and "download all" not in text.lower():
                        # Try to download
                        try:
                            # Short timeout for individual files
                            with page.expect_download(timeout=4000) as download_info:
                                el.click()
                            download = download_info.value
                            path = os.path.join(target_dir, download.suggested_filename)
                            # Avoid overwrites if possible or just let it overwrite
                            download.save_as(path)
                            print(f"    [Deep Fetch] Downloaded: {download.suggested_filename}")
                            download_count += 1
                        except:
                            pass # Not a download link
                except:
                    continue
        except Exception as e:
            print(f"    [Deep Fetch] Individual file scan error: {e}")
            
        return download_count

    def _register_attachments_in_db(self, contract_id, directory):
        """Scan directory and add all files to the database as attachments."""
        if not os.path.exists(directory): return
        
        for root, _, files in os.walk(directory):
            for file in files:
                if file.startswith('.') or file.endswith('.json'): continue
                
                file_path = os.path.abspath(os.path.join(root, file))
                # Add to DB if not already there
                # We use a simple check or just let add_attachment handle it (if it has deduplication)
                try:
                    self.db_manager.add_attachment(
                        contract_id=contract_id,
                        file_name=file,
                        file_path=file_path,
                        url="Extracted via Deep Crawl",
                        download_date=datetime.now().strftime("%Y-%m-%d")
                    )
                    print(f"    [DB] Registered attachment: {file}")
                except Exception as e:
                    print(f"    [DB] Error registering {file}: {e}")


    def _download_file(self, url, target_dir):
        """Deprecated: Legacy urllib download. Keeping for fallback if needed."""
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

    def _extract_external_links(self, text, base_url=None):
        """
        Scan text for URLs that look like file hosts or external portals.
        Resolves relative URLs if base_url is provided.
        """
        if not text: return []
        
        # 1. Regex to find absolute http/https links
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        found_urls = re.findall(url_pattern, text)
        
        # 2. Check for relative links in common portal attributes (href, onclick)
        # This is a bit brute-force but effective for deep crawl
        if base_url:
            rel_patterns = [
                r'href=["\'](/[^"\']+)["\']',
                r'onclick=["\'].*?open_attach\(["\'](/[^"\']+)["\']\)',
                r'location\.href\s*=\s*["\']([^"\']+)["\']'
            ]
            for pattern in rel_patterns:
                rel_matches = re.findall(pattern, text)
                for rel in rel_matches:
                    abs_url = urljoin(base_url, rel)
                    found_urls.append(abs_url)

        target_domains = [
            'drive.google.com', 'dropbox.com', 'box.com', 'onedrive.live.com', 
            'sharepoint.com', 'wetransfer.com', 'army.mil', 'navy.mil', 'af.mil',
            'dla.mil', 'va.gov', 'neco.navy.mil'
        ]
        
        relevant_links = []
        for url in found_urls:
            # Clean trailing punctuation
            url = url.rstrip('.,;:)')
            
            # Filtering: Ignore common assets and non-relevant pages to save time
            junk_patterns = ['.css', '.js', '.jpg', '.png', '.gif', 'login', 'register', 'feedback', 'faq', 'search']
            if any(junk in url.lower() for junk in junk_patterns):
                continue

            # Check if relevant domain OR directly ends in file extension
            is_relevant_domain = any(d in url.lower() for d in target_domains)
            is_file = any(url.lower().endswith(ext) for ext in ['.pdf', '.docx', '.xlsx', '.zip', '.csv'])
            
            if is_relevant_domain or is_file:
                relevant_links.append(url)
        
        # Deduplicate
        unique_links = list(set(relevant_links))
        
        # Prioritization: Sort links so that those containing 'attach', 'doc', or 'soln' come first
        priority_keywords = ['attach', 'doc', 'soln', 'rfq', 'pdf', 'zip']
        def sort_key(u):
            score = 0
            for kw in priority_keywords:
                if kw in u.lower():
                    score -= 1 # Lower is better for sorting (higher priority)
            return score
            
        unique_links.sort(key=sort_key)
                
        return unique_links

    def _recursive_crawl(self, url, depth=0, max_depth=2, target_dir=""):
        """
        Recursively crawls links with multiple fallback strategies for restricted sites.
        """
        if depth > max_depth: return
        
        print(f"    [Deep Crawl] depth={depth} Visiting: {url}")
        
        # Try multiple strategies to access the page
        strategies = [
            self._try_standard_access,
            self._try_with_different_user_agent,
            self._try_alternative_protocol,
            self._try_with_delay
        ]
        
        page_text = None
        new_page = None
        
        for strategy_func in strategies:
            try:
                new_page, page_text = strategy_func(url, target_dir)
                if page_text and "Access Denied" not in page_text:
                    print(f"    [Deep Crawl] ✓ Success with {strategy_func.__name__}")
                    break
                elif new_page:
                    new_page.close()
                    new_page = None
            except Exception as e:
                if new_page:
                    new_page.close()
                    new_page = None
                continue
        
        if not new_page:
            print(f"    [Deep Crawl] ✗ All strategies failed for {url}")
            # Save error info for LLM to know we tried
            self._save_failed_link_info(url, target_dir, depth)
            return
        
        try:
            # Try to grab attachments
            self._deep_download_attachments(new_page, target_dir)
            
            # Find more links if not at max depth
            if depth < max_depth:
                text = new_page.content()
                links = self._extract_external_links(text, base_url=url)
                for link in links:
                    if link not in self.visited_links:
                        self.visited_links.add(link)
                        self._recursive_crawl(link, depth+1, max_depth, target_dir)
        finally:
            if new_page:
                new_page.close()
    
    def _try_standard_access(self, url, target_dir):
        """Standard page access"""
        new_page = self.context.new_page()
        new_page.goto(url, timeout=30000)
        new_page.wait_for_load_state("domcontentloaded")
        page_text = new_page.locator("body").inner_text()
        
        if page_text and len(page_text) > 100:
            self._save_page_content(url, page_text, target_dir, "standard")
        
        return new_page, page_text
    
    def _try_with_different_user_agent(self, url, target_dir):
        """Try with a different user agent"""
        user_agent = random.choice(self.user_agents)
        new_context = self.browser.new_context(user_agent=user_agent)
        new_page = new_context.new_page()
        
        new_page.goto(url, timeout=30000)
        new_page.wait_for_load_state("domcontentloaded")
        page_text = new_page.locator("body").inner_text()
        
        if page_text and len(page_text) > 100:
            self._save_page_content(url, page_text, target_dir, "alt_ua")
        
        new_context.close()
        return new_page, page_text
    
    def _try_alternative_protocol(self, url, target_dir):
        """Try switching http/https"""
        if url.startswith("https://"):
            alt_url = url.replace("https://", "http://")
        else:
            alt_url = url.replace("http://", "https://")
        
        new_page = self.context.new_page()
        new_page.goto(alt_url, timeout=30000)
        new_page.wait_for_load_state("domcontentloaded")
        page_text = new_page.locator("body").inner_text()
        
        if page_text and len(page_text) > 100:
            self._save_page_content(alt_url, page_text, target_dir, "alt_protocol")
        
        return new_page, page_text
    
    def _try_with_delay(self, url, target_dir):
        """Try with delay (rate limiting)"""
        time.sleep(2)  # Wait 2 seconds
        new_page = self.context.new_page()
        new_page.goto(url, timeout=30000)
        new_page.wait_for_load_state("domcontentloaded")
        page_text = new_page.locator("body").inner_text()
        
        if page_text and len(page_text) > 100:
            self._save_page_content(url, page_text, target_dir, "delayed")
        
        return new_page, page_text
    
    def _save_page_content(self, url, page_text, target_dir, method):
        """Save page content to file"""
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', url.split('//')[1][:50])
        text_filename = f"linked_page_{method}_{safe_name}.txt"
        text_path = os.path.join(target_dir, text_filename)
        
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(f"Source URL: {url}\n")
            f.write(f"Access Method: {method}\n")
            f.write("="*80 + "\n\n")
            f.write(page_text)
        
        print(f"    [Deep Crawl] Saved: {text_filename} ({len(page_text)} chars)")
    
    def _save_failed_link_info(self, url, target_dir, depth):
        """Save info about failed link attempts"""
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', url.split('//')[1][:50])
        text_filename = f"FAILED_ACCESS_depth{depth}_{safe_name}.txt"
        text_path = os.path.join(target_dir, text_filename)
        
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(f"FAILED TO ACCESS: {url}\n")
            f.write(f"Depth: {depth}\n")
            f.write("="*80 + "\n\n")
            f.write("This link was found in the solicitation but could not be accessed.\n")
            f.write("Possible reasons: firewall, authentication required, or site down.\n")
            f.write("\nLLM: Please try to infer missing data from other sources or mark as unavailable.\n")
        
        print(f"    [Deep Crawl] Saved failure info: {text_filename}")
    def _process_external_link(self, page, url, save_dir):
        """
        Visit an external link and attempt to download files using Playwright.
        Also saves page content for AttachmentReaderAgent extraction.
        """
        print(f"    [Deep Link] Visiting: {url}")
        try:
            # We use the existing page to share session/cookies if applicable, 
            # BUT we must be careful not to losing context.
            # Ideally, we open a new tab/page for this external excursion.
            # check if self.context exists
            ex_page = self.context.new_page()
            
            try:
                # 1. Try Direct Download
                try:
                    with ex_page.expect_download(timeout=10000) as download_info:
                        ex_page.goto(url, timeout=20000)
                    
                    download = download_info.value
                    safe_name = f"external_{int(time.time())}_{download.suggested_filename}"
                    download.save_as(os.path.join(save_dir, safe_name))
                    print(f"    [Deep Link] Direct Download Success: {safe_name}")
                    return
                except:
                    # Page loaded normally (no auto download)
                    pass
                
                # 2. Page Analysis - Save content for extraction
                ex_page.wait_for_load_state("domcontentloaded", timeout=5000)
                
                # CRITICAL: Save page content as text file
                try:
                    page_text = ex_page.locator("body").inner_text()
                    if page_text and len(page_text) > 100:
                        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', url.split('//')[1][:50])
                        text_filename = f"external_link_{safe_name}.txt"
                        text_path = os.path.join(save_dir, text_filename)
                        
                        with open(text_path, 'w', encoding='utf-8') as f:
                            f.write(f"Source URL: {url}\n")
                            f.write("="*80 + "\n\n")
                            f.write(page_text)
                        
                        print(f"    [Deep Link] Saved page content: {text_filename} ({len(page_text)} chars)")
                except Exception as e:
                    print(f"    [Deep Link] Could not save page text: {e}")
                
                # Look for explicit download buttons
                buttons = ex_page.get_by_text("Download", exact=False)
                if buttons.count() > 0:
                     print(f"    [Deep Link] Found 'Download' elements. Clicking top one...")
                     try:
                         with ex_page.expect_download(timeout=10000) as download_info:
                             buttons.first.click()
                         download = download_info.value
                         safe_name = f"external_{int(time.time())}_{download.suggested_filename}"
                         download.save_as(os.path.join(save_dir, safe_name))
                         print(f"    [Deep Link] Click Download Success: {safe_name}")
                     except:
                         pass
                         
            except Exception as e:
                print(f"    [Deep Link] Failed to process {url}: {e}")
            finally:
                ex_page.close()
                
        except Exception as e:
            print(f"    [Deep Link] Critical Error: {e}")

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

    def search_for_links(self, search_term, start_page=1, num_pages=1):
        """
        Searches SAM.gov and returns a list of solicitation URLs.
        Supports pagination offset via start_page.
        """
        print(f"--- Searching SAM.gov for URLs: {search_term} (Start: {start_page}, Count: {num_pages}) ---")
        
        try:
            # Construct URL with correct nested parameters for SAM.gov Angular app
            # Previous error: TypeError: H.simpleSearch.keywordTags.map is not a function (caused by passing string instead of array of objects)
            
            base_params = {
                "index": "opp",
                "page": str(start_page),
                "sort": "-modifiedDate",
                "pageSize": "25",
                "sfm[simpleSearch][keywordRadio]": "ALL",
                "sfm[simpleSearch][keywordTags][0][key]": search_term,
                "sfm[simpleSearch][keywordTags][0][value]": search_term,
                "sfm[simpleSearch][keywordEditorTextarea]": "",
                "sfm[status][is_active]": "true"
            }
            
            encoded_params = urllib.parse.urlencode(base_params)
            base_url = f"https://sam.gov/search/?{encoded_params}"
            
            logger = logging.getLogger("SamGovAgent")
            print(f"Navigating to: {base_url}")
            
            # RETRY LOGIC for Connection Stability
            MAX_RETRIES = 3
            for attempt in range(MAX_RETRIES):
                try:
                    self.page.goto(base_url, timeout=60000, wait_until="domcontentloaded")
                    
                    # Wait for results or "No results found" message
                    # app-opportunity-result = Success
                    # .sds-alert = Possible "No results" or error
                    self.page.wait_for_selector("app-opportunity-result, .sds-alert--error, .sds-alert--info", timeout=60000)
                    
                    if self.page.is_visible(".sds-alert--error") or self.page.is_visible(".sds-alert--info"):
                        # Check strictly for "No results found" text
                         text = self.page.locator(".sds-alert").first.text_content()
                         if "No results found" in text:
                             print(f"  Search returned no results for '{search_term}'.")
                             return []
                    
                    print("Search results loaded.")
                    break # Success
                except Exception as e:
                    print(f"  Attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
                    if attempt < MAX_RETRIES - 1:
                        sleep_time = 5 * (attempt + 1)
                        print(f"  Waiting {sleep_time}s before retry...")
                        time.sleep(sleep_time)
                    else:
                        print("  Max retries reached. Aborting search for this keyword.")
                        return [] # Fail gracefully
            
        except Exception as e:
            print(f"Error accessing search page: {e}")
            return []

        all_urls = []
        current_page = start_page
        end_page = start_page + num_pages - 1
        
        while current_page <= end_page:
            print(f"Extracting links from page {current_page}...")
            
            try:
                results = self.page.query_selector_all("app-opportunity-result h3 a")
                page_urls = []
                for link in results:
                    href = link.get_attribute("href")
                    if href:
                        if href.startswith('/'):
                            href = "https://sam.gov" + href
                        page_urls.append(href)
                
                print(f"  Found {len(page_urls)} links.")
                all_urls.extend(page_urls)

                if len(page_urls) == 0:
                    break
                
                if current_page >= end_page:
                    break

                # Next Page
                try:
                    next_btn = self.page.query_selector("//button[contains(text(), 'Next')]")
                    if next_btn and not next_btn.is_disabled():
                        next_btn.click()
                        self.page.wait_for_load_state("networkidle")
                        time.sleep(3)
                        current_page += 1
                    else:
                        print("No Next button or disabled.")
                        break
                except:
                    break
            except Exception as e:
                print(f"Error extracting links: {e}")
                break
                
        return list(set(all_urls)) # Deduplicate

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

    def _find_and_download_hidden_links(self, page, target_dir):
        """
        Finds and downloads links that say 'Click here', 'Download', etc.
        """
        try:
            # Find ALL clickable elements
            links = page.query_selector_all('a, button, [role="button"]')
            
            for link in links:
                text = (link.inner_text() or "").lower()
                
                # Target: "Click here", "Additional Documents", "Download", etc.
                if any(x in text for x in ["click here", "additional", "download", "documents", "attachments"]):
                    href = link.get_attribute('href')
                    
                    if href:
                        print(f"    [Hidden Link] Found: {text} -> {href}")
                        
                        # Try to download
                        try:
                            with page.expect_download(timeout=15000) as download_info:
                                link.click()
                            
                            download = download_info.value
                            safe_name = f"hidden_link_{download.suggested_filename}"
                            download.save_as(os.path.join(target_dir, safe_name))
                            print(f"    [Downloaded] {safe_name}")
                        except:
                            # Not a download link, try navigation
                            # Be careful not to navigate main page away if it's the same page
                            # But here we assume it opens in new tab or we handle it safely?
                            # The code snippet creates a NEW PAGE context which is safe.
                            try:
                                new_page = self.context.new_page()
                                new_page.goto(href, timeout=30000)
                                
                                # Extract and save
                                content = new_page.content()
                                safe_name = f"external_link_{int(time.time())}.txt"
                                with open(os.path.join(target_dir, safe_name), 'w') as f:
                                    f.write(content)
                                
                                new_page.close()
                                print(f"    [Saved] {safe_name}")
                            except Exception as nav_e:
                                print(f"    [Hidden Link] Navigation failed: {nav_e}")
        
        except Exception as e:
            print(f"    [Error] Finding hidden links: {e}")

    def process_detail_page(self, url):
        """
        Opens a new page to scrape the detail, preventing disruption of the main search flow.
        Includes a fallback to local data if the scrape fails but data exists.
        """
        # Robust ID extraction from SAM.gov URL (pre-scrape)
        match = re.search(r'/opp/([a-f0-9]+)/view', url)
        if match:
            contract_id = match.group(1)[:10]
        else:
            contract_id = hashlib.md5(url.encode()).hexdigest()[:10]
            
        contract_dir = os.path.join(config.SOLICITATION_DATA_DIR, contract_id)
        
        detail_page = None
        sol_data = None
        
        try:
            print(f"  Visiting {url}...")
            detail_page = self.context.new_page()
            detail_page.goto(url, timeout=45000)
            detail_page.wait_for_selector("h1", timeout=30000)
            
            # CRITICAL: Wait for description to load
            try:
                detail_page.wait_for_selector("#desc", timeout=5000)
            except:
                print("  Warning: #desc selector not found, continuing with body text...")

            title = detail_page.locator("h1").first.text_content().strip()
            
            # Prefer full body text but ensure #desc is captured
            page_text = detail_page.locator("body").inner_text()
            
            # Explicitly append #desc text if it might be missing from body scan
            try:
                desc_text = detail_page.locator("#desc").inner_text()
                if desc_text not in page_text:
                    page_text += "\n\n--- FORCED DESCRIPTION EXTRACTION ---\n\n" + desc_text
            except:
                pass
            
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
            
            # Deep Fetch (Playwright)
            self._deep_download_attachments(detail_page, attachment_dir)
            self._find_and_download_hidden_links(detail_page, attachment_dir)
            
            # Deep Link Following (Robust)
            # Use the new helper method to find and fetch external links
            external_links = self._extract_external_links(detail_page.content(), base_url=url)
            if external_links:
                print(f"    [Deep Dive] Found {len(external_links)} potential external links. analyzing...")
                clicked_count = 0
                for link in external_links:
                    if clicked_count >= 10: break # Safety limit (increased for portals)
                    # Filter out purely navigational/junk links if regex wasn't enough
                    if "sam.gov" in link and "opp" not in link: continue 
                    
                    self._process_external_link(detail_page, link, attachment_dir) 
                    
                    # New Recursive Crawl for critical external portals
                    if depth_enabled := False: 
                         # self.visited_links is a set on the class, careful about resets
                         # Use at least depth 2 for portals to reach the actual files
                         self._recursive_crawl(link, depth=1, max_depth=2, target_dir=attachment_dir)

                    clicked_count += 1

            # --- REGISTER ALL DOWNLOADS IN DB ---
            self._register_attachments_in_db(contract_id, attachment_dir)
            # Also register the main description and metadata as "docs" if helpful
            # But primarily we want all files in attachment_dir


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
            # FALLBACK to local data (contract_id and contract_dir are already set above)
            metadata_path = os.path.join(contract_dir, "metadata.json")
            if os.path.exists(metadata_path):
                print(f"  [Fallback] Loading local data for {contract_id} from {contract_dir}...")
                with open(metadata_path, 'r') as f:
                    meta = json.load(f)
                
                desc_path = os.path.join(contract_dir, "description.txt")
                desc = ""
                if os.path.exists(desc_path):
                    with open(desc_path, 'r') as f:
                        desc = f.read()
                
                sol_data = {
                    'title': meta.get('title', 'Unknown Title'),
                    'url': url,
                    'description': desc[:3000],
                    'contract_id': contract_id
                }
            else:
                print(f"  [Fallback] No local data found for {contract_id} at {contract_dir}")
        finally:
            if detail_page:
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
