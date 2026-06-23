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
import requests
from bs4 import BeautifulSoup
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


    def _download_external_document(self, url: str, save_dir: str) -> str:
        """
        Download external document from URL.
        Returns path to downloaded file.
        """
        try:
            # User agent rotation for requests
            headers = {
                'User-Agent': random.choice(self.user_agents)
            }
            
            response = requests.get(url, headers=headers, timeout=30, verify=False)
            response.raise_for_status()
            
            # Determine filename
            if 'Content-Disposition' in response.headers:
                filename = response.headers['Content-Disposition'].split('filename=')[1].strip('"')
            else:
                filename = url.split('/')[-1] or 'external_document.pdf'
            
            # Ensure valid filename
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            
            filepath = os.path.join(save_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logging.info(f"    Downloaded: {filename}")
            return filepath
            
        except Exception as e:
            logging.error(f"    Failed to download {url}: {e}")
            return None

    def _extract_wage_determination(self, soup, save_dir: str):
        """
        Specifically hunt for wage determination documents.
        """
        wd_data = {'found': False, 'file_path': None, 'wd_number': None}
        
        # Look for WD links
        wd_patterns = [
            r'wage\s*determination',
            r'WD[\s\-]?\d+',
            r'prevailing\s*wage'
        ]
        
        for pattern in wd_patterns:
            links = soup.find_all('a', string=re.compile(pattern, re.IGNORECASE))
            for link in links:
                url = link.get('href')
                if url:
                    if url.startswith('/'):
                        url = 'https://sam.gov' + url
                    
                    filepath = self._download_external_document(url, save_dir)
                    if filepath:
                        wd_data['found'] = True
                        wd_data['file_path'] = filepath
                        
                        # Try to extract WD number from text
                        wd_num_match = re.search(r'WD[\s\-]?(\d+)', link.text)
                        if wd_num_match:
                            wd_data['wd_number'] = wd_num_match.group(1)
                        
                        return wd_data
        
        return wd_data

    def _extract_sf1449_data(self, soup):
        """
        Extract structured data from SF 1449 form if present.
        """
        sf1449_data = {
            'found': False,
            'clins': [],
            'total_amount': None
        }
        
        # Look for SF 1449 indicators
        if soup.find(string=re.compile(r'SF\s*1449', re.IGNORECASE)):
            sf1449_data['found'] = True
            
            # Extract CLIN table
            tables = soup.find_all('table')
            for table in tables:
                headers = [th.text.strip().upper() for th in table.find_all('th')]
                
                if 'CLIN' in headers or 'ITEM' in headers:
                    rows = table.find_all('tr')[1:]  # Skip header
                    for row in rows:
                        cells = [td.text.strip() for td in row.find_all('td')]
                        if len(cells) >= 4:
                            sf1449_data['clins'].append({
                                'clin': cells[0],
                                'description': cells[1],
                                'quantity': cells[2],
                                'unit': cells[3] if len(cells) > 3 else 'EA'
                            })
            
            logging.info(f"    Extracted {len(sf1449_data['clins'])} CLINs from SF 1449")
        
        return sf1449_data

    def _extract_external_links(self, soup):
        """
        Find all external document links that need to be crawled.
        """
        external_links = []
        
        if not soup:
            return external_links

        # Look for common patterns
        link_patterns = [
            ('a', 'href', re.compile(r'.*\.pdf$', re.IGNORECASE)),
            ('a', 'href', re.compile(r'.*view.*document.*', re.IGNORECASE)),
            ('a', 'href', re.compile(r'.*attachment.*', re.IGNORECASE)),
            ('a', 'href', re.compile(r'.*download.*', re.IGNORECASE))
        ]
        
        for tag, attr, pattern in link_patterns:
            links = soup.find_all(tag, {attr: pattern})
            for link in links:
                url = link.get(attr)
                if url and url not in external_links:
                    # Make absolute URL
                    if url.startswith('/'):
                        url = 'https://sam.gov' + url
                    external_links.append(url)
        
        # Filter out junk
        filtered_links = []
        junk_patterns = ['.css', '.js', '.jpg', '.png', '.gif', 'login', 'register', 'feedback', 'faq', 'search']
        for url in external_links:
             if not any(junk in url.lower() for junk in junk_patterns):
                 filtered_links.append(url)

        logging.info(f"  Found {len(filtered_links)} external links to crawl")
        return filtered_links

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
                soup = BeautifulSoup(new_page.content(), 'html.parser')
                links = self._extract_external_links(soup)
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
    def _extract_description_comprehensive(self, soup) -> str:
        """
        Comprehensive description extraction from SAM.gov pages.
        Tries multiple strategies to capture all relevant text.
        """
        description_parts = []
        
        # Strategy 1: Look for main description container
        desc_selectors = [
            {'class': re.compile(r'description', re.IGNORECASE)},
            {'id': re.compile(r'description', re.IGNORECASE)},
            {'class': re.compile(r'details', re.IGNORECASE)},
            {'class': re.compile(r'content', re.IGNORECASE)},
        ]
        
        for selector in desc_selectors:
            desc_elem = soup.find('div', selector)
            if desc_elem:
                text = desc_elem.get_text(separator='\n', strip=True)
                if len(text) > 100:
                    description_parts.append(f"=== Main Description ===\n{text}\n")
                    break
        
        # Strategy 2: Extract ALL section elements with substantial text
        sections = soup.find_all(['section', 'article', 'div'], 
                                class_=re.compile(r'section|detail|info', re.IGNORECASE))
        
        for section in sections:
            # Get section header if exists
            header = section.find(['h2', 'h3', 'h4', 'strong'])
            header_text = header.get_text(strip=True) if header else "Section"
            
            # Get section content
            section_text = section.get_text(separator='\n', strip=True)
            
            # Only add if substantial (>200 chars) and not already captured
            if len(section_text) > 200:
                # Check if not duplicate
                if not any(section_text[:100] in part for part in description_parts):
                    description_parts.append(f"\n=== {header_text} ===\n{section_text}\n")
        
        # Strategy 3: Look for key information fields
        key_fields = [
            'Notice ID',
            'Solicitation Number',
            'Posted Date',
            'Response Date',
            'Classification Code',
            'NAICS',
            'Set Aside',
            'Place of Performance'
        ]
        
        field_data = []
        for field in key_fields:
            # Look for labels
            label = soup.find(string=re.compile(f'^{field}', re.IGNORECASE))
            if label:
                # Get parent and find value
                parent = label.find_parent()
                if parent:
                    # Try sibling
                    sibling = parent.find_next_sibling()
                    if sibling:
                        value = sibling.get_text(strip=True)
                        field_data.append(f"{field}: {value}")
                    else:
                        # Try next element in parent
                        value = parent.get_text(strip=True)
                        value = value.replace(field, '').strip()
                        if value:
                            field_data.append(f"{field}: {value}")
        
        if field_data:
            description_parts.insert(0, "=== Solicitation Information ===\n" + "\n".join(field_data) + "\n")
        
        # Strategy 4: Extract table data (often contains requirements)
        tables = soup.find_all('table')
        for idx, table in enumerate(tables):
            try:
                # Convert table to readable text
                rows = table.find_all('tr')
                if len(rows) > 1:  # Has actual data
                    table_text = f"\n=== Table {idx+1} ===\n"
                    for row in rows:
                        cells = row.find_all(['th', 'td'])
                        row_text = " | ".join([cell.get_text(strip=True) for cell in cells])
                        if row_text:
                            table_text += row_text + "\n"
                    
                    if len(table_text) > 100:
                        description_parts.append(table_text)
            except:
                continue
        
        # Strategy 5: If still empty, grab all paragraph text
        if len(description_parts) == 0:
            all_paragraphs = soup.find_all('p')
            para_texts = [p.get_text(strip=True) for p in all_paragraphs if len(p.get_text(strip=True)) > 50]
            if para_texts:
                description_parts.append("=== Content ===\n" + "\n\n".join(para_texts))
        
        # Combine all parts
        full_description = "\n".join(description_parts)
        
        return full_description if full_description.strip() else None

    def _extract_notice_id(self, soup, html_content: str = None) -> str:
        """
        Extract the real Notice ID / Solicitation Number from the sam.gov page.
        Returns the real ID (e.g. 'N0010425QNF13') or None if not found.
        """
        # Strategy 1: Look for label text in soup
        notice_patterns = [
            re.compile(r'Notice ID', re.IGNORECASE),
            re.compile(r'Solicitation Number', re.IGNORECASE),
            re.compile(r'Contract Number', re.IGNORECASE),
        ]

        for pattern in notice_patterns:
            label = soup.find(string=pattern)
            if label:
                parent = label.find_parent()
                if parent:
                    sibling = parent.find_next_sibling()
                    if sibling:
                        value = sibling.get_text(strip=True)
                        if value and len(value) > 3:
                            return value
                    # Fallback: extract value from parent text
                    value = parent.get_text(strip=True)
                    value = pattern.sub('', value).strip()
                    if value and len(value) > 3:
                        return value

        # Strategy 2: Look for specific HTML patterns in sam.gov pages
        # sam.gov uses <strong> or <span> near label elements
        if html_content:
            # Match patterns like "Notice ID N0010425QNF13" or "Solicitation #: N0010425QNF13"
            m = re.search(r'Notice\s+ID[:\s]+([A-Z0-9][\w-]+)', html_content, re.IGNORECASE)
            if m:
                return m.group(1)
            m = re.search(r'Solicitation\s+Number[:\s]+([A-Z0-9][\w-]+)', html_content, re.IGNORECASE)
            if m:
                return m.group(1)
            m = re.search(r'Contract\s+Number[:\s]+([A-Z0-9][\w-]+)', html_content, re.IGNORECASE)
            if m:
                return m.group(1)

        return None

    def process_detail_page(self, url: str):
        """
        Enhanced version with comprehensive crawling using Playwright and BS4.
        """
        logging.info(f"\n{'='*80}")
        logging.info(f"ENHANCED DETAIL PAGE PROCESSING: {url}")
        logging.info(f"{'='*80}\n")

        detail_page = None
        try:
            # Use a new page (tab) to preserve search results on main page
            detail_page = self.context.new_page()
            detail_page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Wait a bit for dynamic content
            try:
                detail_page.wait_for_selector("main", timeout=10000)
            except:
                pass # Continue even if main not found
            time.sleep(3)

            # Get HTML content for BS4
            html_content = detail_page.content()
            soup = BeautifulSoup(html_content, 'html.parser')

        except Exception as e:
            logging.error(f"Failed to load page: {e}")
            if detail_page: detail_page.close()
            return None

        try:
            # Extract real Notice ID first, fallback to URL UUID
            real_notice_id = self._extract_notice_id(soup, html_content)
            url_uuid = url.split('/')[-2] if '/opp/' in url else f"contract_{int(time.time())}"

            if real_notice_id:
                contract_id = real_notice_id
                logging.info(f"  ✓ Extracted real Notice ID: {contract_id}")
            else:
                contract_id = url_uuid
                logging.warning(f"  ✗ No Notice ID found, using URL fragment: {contract_id}")
            
            # Create save directory
            save_dir = os.path.join(config.SOLICITATION_DATA_DIR, contract_id)
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
                
            attachment_dir = os.path.join(save_dir, "attachments")
            os.makedirs(attachment_dir, exist_ok=True)
            
            solicitation_data = {
                'contract_id': contract_id,
                'url': url,
                'title': None,
                'description': None,
                'attachments': [],
                'external_links': [],
                'wage_determination': None,
                'sf1449_data': None
            }
            
            # 1. Extract title
            title_elem = soup.find('h1')
            if title_elem:
                solicitation_data['title'] = title_elem.text.strip()
                logging.info(f"  Title: {solicitation_data['title'][:80]}...")
            
            # 2. Extract description (ENHANCED)
            logging.info(f"  [Enhanced] Extracting description...")
            full_description = self._extract_description_comprehensive(soup)
            
            if full_description:
                desc_path = os.path.join(save_dir, "description.txt")
                with open(desc_path, "w", encoding="utf-8") as f:
                    f.write(full_description)
                solicitation_data['description'] = full_description[:500]  # Preview
                logging.info(f"  ✓ Description saved ({len(full_description)} chars)")
            else:
                logging.warning(f"  ✗ Could not extract description")

            # 3. Extract SF 1449 data
            logging.info(f"  [Enhanced] Extracting SF 1449 data...")
            sf1449_data = self._extract_sf1449_data(soup)
            solicitation_data['sf1449_data'] = sf1449_data
            
            # 4. Download standard attachments (Using existing Playwright method)
            logging.info(f"  [Standard] Downloading attachments...")
            # Use existing Playwright-based download logic with the DETAIL PAGE
            download_count = self._deep_download_attachments(detail_page, attachment_dir)
            # Register them in DB/List
            self._register_attachments_in_db(contract_id, attachment_dir)
            logging.info(f"    Downloaded {download_count} standard attachments")
            
            # 5. Extract and download external links (New BS4 method)
            logging.info(f"  [Enhanced] Crawling external links...")
            external_links = self._extract_external_links(soup)
            for link in external_links:
                try:
                    filepath = self._download_external_document(link, attachment_dir)
                    if filepath:
                        solicitation_data['external_links'].append({
                            'url': link,
                            'file_path': filepath
                        })
                        # Add to DB
                        self.db_manager.add_attachment(
                            contract_id=contract_id,
                            file_name=os.path.basename(filepath),
                            file_path=filepath,
                            url=link,
                            download_date=datetime.now().strftime("%Y-%m-%d")
                        )
                except Exception as e:
                    logging.error(f"Failed to process external link {link}: {e}")

            logging.info(f"    Downloaded {len(solicitation_data['external_links'])} external documents")
            
            # 6. Hunt for wage determination
            logging.info(f"  [Enhanced] Searching for wage determination...")
            wd_data = self._extract_wage_determination(soup, attachment_dir)
            solicitation_data['wage_determination'] = wd_data
            if wd_data['found']:
                logging.info(f"    ✓ Found WD: {wd_data.get('wd_number', 'Unknown number')}")
                # Add to DB
                if wd_data.get('file_path'):
                    self.db_manager.add_attachment(
                        contract_id=contract_id,
                        file_name=os.path.basename(wd_data['file_path']),
                        file_path=wd_data['file_path'],
                        url="Wage Determination Search",
                        download_date=datetime.now().strftime("%Y-%m-%d")
                    )
            
            logging.info(f"\n{'='*80}")
            logging.info(f"EXTRACTION COMPLETE: {contract_id}")
            logging.info(f"  - Standard Attachments: {download_count}")
            logging.info(f"  - External Documents: {len(solicitation_data['external_links'])}")
            logging.info(f"  - SF 1449 CLINs: {len(sf1449_data.get('clins', []))}")
            logging.info(f"  - Wage Determination: {'Found' if wd_data['found'] else 'Not Found'}")
            logging.info(f"{'='*80}\n")
            
            return solicitation_data

        except Exception as e:
             logging.error(f"Error processing detail page {url}: {e}")
             return None
        finally:
            if detail_page:
                detail_page.close()

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
