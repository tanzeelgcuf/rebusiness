import sys
import os
import time
import json
import csv
import hashlib
import urllib.request
import urllib.error
import zipfile
import re
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import config
import capsolver


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

    def _solve_captcha(self, page):
        """
        Detects and solves reCAPTCHA v2/v3 using CapSolver.
        """
        try:
            # Check for reCAPTCHA frames or elements
            iframe = page.query_selector("iframe[src*='google.com/recaptcha']")
            if iframe:
                print("    [CAPTCHA] Detected reCAPTCHA. Attempting to solve...")
                
                # Get sitekey
                sitekey_frame = page.frame_locator("iframe[src*='google.com/recaptcha']").first
                # This is a simplification; often sitekey is in the main page source div
                # A more robust way:
                sitekey_elem = page.query_selector("[data-sitekey]")
                sitekey = sitekey_elem.get_attribute("data-sitekey") if sitekey_elem else None
                
                if not sitekey:
                    # Fallback regex
                    content = page.content()
                    match = re.search(r'data-sitekey=["\'](.+?)["\']', content)
                    if match:
                        sitekey = match.group(1)
                
                if sitekey:
                    print(f"    [CAPTCHA] Found sitekey: {sitekey}")
                    capsolver.api_key = os.getenv("CAPSOLVER_API_KEY") 
                    if not capsolver.api_key:
                        print("    [CAPTCHA] Error: CAPSOLVER_API_KEY not set.")
                        return

                    solution = capsolver.solve({
                        "type": "ReCaptchaV2TaskProxyLess",
                        "websiteURL": page.url,
                        "websiteKey": sitekey
                    })
                    
                    token = solution.get("gRecaptchaResponse")
                    if token:
                        print("    [CAPTCHA] Solved! Injecting token...")
                        page.evaluate(f'document.getElementById("g-recaptcha-response").innerHTML="{token}";')
                        # Sometimes need to call a callback function
                        # page.evaluate(f'___grecaptcha_cfg.clients[0].aa.l.callback("{token}")') 
                        # Click verify/submit if exists
                        # This part is highly site-specific
                else:
                    print("    [CAPTCHA] Could not find sitekey.")
        except Exception as e:
            print(f"    [CAPTCHA] Error solving: {e}")


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

    def _extract_external_links(self, text):
        """
        Scan text for URLs that look like file hosts or external portals.
        """
        if not text: return []
        
        # Regex to find http/https links
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        found_urls = re.findall(url_pattern, text)
        
        target_domains = [
            'drive.google.com', 'dropbox.com', 'box.com', 'onedrive.live.com', 
            'sharepoint.com', 'wetransfer.com', 'army.mil', 'navy.mil', 'af.mil',
            'dla.mil', 'va.gov' # Agency sites often host files directly
        ]
        
        relevant_links = []
        for url in found_urls:
            # Clean trailing punctuation
            url = url.rstrip('.,;:)')
            
            # Check if relevant domain OR directly ends in file extension
            is_relevant_domain = any(d in url.lower() for d in target_domains)
            is_file = any(url.lower().endswith(ext) for ext in ['.pdf', '.docx', '.xlsx', '.zip', '.csv'])
            
            if is_relevant_domain or is_file:
                relevant_links.append(url)
                
        return list(set(relevant_links)) # Deduplicate

    def _recursive_crawl(self, url, depth=0, max_depth=2, target_dir=""):
        """
        Recursively crawls links to find more attachments.
        """
        if depth > max_depth: return
        
        print(f"    [Deep Crawl] depth={depth} Visiting: {url}")
        new_page = self.context.new_page()
        try:
            new_page.goto(url, timeout=30000)
            # Try to grab attachments here
            self._deep_download_attachments(new_page, target_dir)
            
            # Find more links if not at max depth
            if depth < max_depth:
                text = new_page.content()
                links = self._extract_external_links(text)
                for link in links:
                    # Filter loops
                     if link not in self.visited_links:
                        self.visited_links.add(link)
                        self._recursive_crawl(link, depth+1, max_depth, target_dir)
        except Exception as e:
            print(f"    [Deep Crawl] Error on {url}: {e}")
        finally:
            new_page.close()


    def _process_external_link(self, page, url, save_dir):
        """
        Visit an external link and attempt to download files using Playwright.
        Robustly handles direct downloads and 'Click to Download' pages.
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
                
                # 2. Page Analysis
                ex_page.wait_for_load_state("domcontentloaded", timeout=5000)
                
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

    def process_detail_page(self, url):
        """
        Opens a new page to scrape the detail, preventing disruption of the main search flow.
        """
        detail_page = self.context.new_page()
        sol_data = None
        try:
            print(f"  Visiting {url}...")
            detail_page.goto(url, timeout=45000)
            
            # Check for Captcha on load
            self._solve_captcha(detail_page)

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
            
            # Deep Fetch (Playwright)
            self._deep_download_attachments(detail_page, attachment_dir)
            
            # Deep Link Following (Robust)
            # Use the new helper method to find and fetch external links
            external_links = self._extract_external_links(page_text)
            if external_links:
                print(f"    [Deep Dive] Found {len(external_links)} potential external links. analyzing...")
                clicked_count = 0
                for link in external_links:
                    if clicked_count >= 5: break # Safety limit
                    # Filter out purely navigational/junk links if regex wasn't enough
                    if "sam.gov" in link and "opp" not in link: continue 
                    
                    self._process_external_link(self.page, link, attachment_dir) 
                    
                    # New Recursive Crawl for critical external portals
                    if depth_enabled := True: # Enable logic switch
                         self.visited_links = set()
                         self._recursive_crawl(link, depth=1, max_depth=2, target_dir=attachment_dir)

                    clicked_count += 1

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
