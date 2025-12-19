import os
import time
import json
import mimetypes
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse, urljoin, unquote
import requests
import zipfile
import re
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException, WebDriverException
from requests.exceptions import RequestException, HTTPError # Import for robust requests

# Assuming database_manager.py is in the parent directory
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from database_manager import DatabaseManager

class DescriptionDownloaderAgent:
    MAX_CRAWL_DEPTH = 3 # Increased default crawl depth
    def __init__(self, headless=True, download_dir="downloads"):
        self.headless = headless
        self.download_dir = os.path.abspath(download_dir)
        os.makedirs(self.download_dir, exist_ok=True)
        self.driver = self._initialize_driver()
        self.db_manager = DatabaseManager()
        self.visited_urls = set()

    def _initialize_driver(self):
        print("Initializing Chrome WebDriver...")
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new") # Use the new headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        # Add more arguments for stability
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--single-process") # May help on some systems, can remove if issues persist
        chrome_options.add_argument("--disable-browser-side-navigation")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument('--remote-debugging-port=9222') # Useful for debugging if needed
        prefs = {"download.default_directory": self.download_dir, "download.prompt_for_download": False, "plugins.always_open_pdf_externally": True}
        chrome_options.add_experimental_option("prefs", prefs)
        try:
            print("Attempting to get ChromeDriver...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(60) # Set page load timeout
            print("WebDriver initialized successfully.")
            return driver
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            raise

    def _get_contract_id_from_url(self, url):
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        if 'contract' in path_parts and 'opp' in path_parts:
            try:
                return path_parts[path_parts.index('opp') + 1]
            except (ValueError, IndexError):
                pass
        return None

    def _handle_cookie_banner(self):
        try:
            cookie_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Agree')]" ))
            )
            cookie_button.click()
            print("Clicked cookie consent button.")
            time.sleep(1) # Wait for banner to disappear
        except (TimeoutException, NoSuchElementException):
            print("No cookie consent banner found.")

    def _wait_for_download_complete(self, initial_files, timeout=180, extension=None):
        """Waits for a new file to appear and complete in the download directory."""
        seconds = 0
        while seconds < timeout:
            current_files = os.listdir(self.download_dir)
            new_files = [f for f in current_files if f not in initial_files]
            
            if extension:
                new_files = [f for f in new_files if f.lower().endswith(extension)]

            completed_new_files = [f for f in new_files if not f.endswith('.crdownload') and not f.endswith('.tmp')] # Also check for .tmp files

            if completed_new_files:
                # Ensure the file size is not 0 (still being written)
                full_path = os.path.join(self.download_dir, completed_new_files[0])
                if os.path.getsize(full_path) > 0:
                    return full_path
            
            time.sleep(1)
            seconds += 1
        return None

    def _download_all_attachments_as_zip(self, contract_id):
        print("\n--- Attempting to download all attachments as zip. ---")
        download_all_selectors = [
            "//div[@id='files']//button[contains(text(), 'Download All')]", # Specific to files section
            "//button[contains(text(), 'Download All')]", # More general
            "//button[contains(., 'Download All')]",
            "//button[contains(@aria-label, 'Download All')]",
            "//button[contains(@aria-label, 'Download All attachments')]",
            "//app-attachments//button[contains(normalize-space(.), 'Download All')]" # New broader selector
        ]
        
        download_all_button = None
        for selector in download_all_selectors:
            try:
                # Wait for the button to be present and clickable
                download_all_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                if download_all_button:
                    print(f"Found 'Download All' button with selector: {selector}.")
                    break
            except (NoSuchElementException, TimeoutException):
                print(f"Selector '{selector}' did not find a clickable button.")
                continue

        if not download_all_button:
            print("Could not find 'Download All' button with any of the selectors.")
            return None

        try:
            initial_files_in_dir = os.listdir(self.download_dir)
            self.driver.execute_script("arguments[0].scrollIntoView(true);", download_all_button)
            time.sleep(1) # Give a moment for scroll
            download_all_button.click()
            print("Clicked 'Download All' button.")

            zip_file_path = self._wait_for_download_complete(initial_files_in_dir, timeout=300, extension=".zip") # Increased timeout

            if zip_file_path:
                print(f"Successfully downloaded zip file: {zip_file_path}")
                unzipped_files = []
                with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                    zip_ref.extractall(self.download_dir)
                    for file_info in zip_ref.infolist():
                        unzipped_path = os.path.join(self.download_dir, file_info.filename)
                        # Only add if it's an actual file and not a directory inside the zip
                        if not file_info.is_dir():
                            unzipped_files.append(unzipped_path)
                            self.db_manager.add_attachment(contract_id=contract_id, file_name=file_info.filename, file_path=unzipped_path, url=None, download_date=time.time())
                os.remove(zip_file_path)
                print(f"Successfully extracted {len(unzipped_files)} files from zip archive. Removed original zip.")
                return unzipped_files
            else:
                print("'Download All' button was clicked, but zip file was not found in download directory within timeout.")
                return []
        except Exception as e:
            print(f"An error occurred with the 'Download All' process: {e}")
            return None

    def _download_individual_attachments(self, contract_id):
        print("\n--- Attempting to download attachments individually. ---")
        downloaded_files = []
        # More robust selectors for attachment links within the table
        attachment_links_selectors = [
            "//div[@id='files']//a[contains(@class, 'file-link')]", # Specific to the table in files section
            "//app-attachments//a[contains(@class, 'file-link')]", # Broader within app-attachments
            "//a[contains(@href, 'api.sam.gov/content')]", # Keep if still relevant for some structures
            "//a[contains(@href, '/attachments/')]",
            "//div[@id='files']//a[contains(@href, '/api/documents/contract/')]", # New selector for API document links
            "//app-attachments//a[contains(@href,'.pdf') or contains(@href,'.docx') or contains(@href,'.xlsx') or contains(@href,'.zip') or contains(@href,'.csv') or contains(@href,'.doc') or contains(@href,'.txt')]", # New broader selector within app-attachments
            "//a[contains(text(), '.pdf') or contains(text(), '.docx') or contains(text(), '.xlsx') or contains(text(), '.zip') or contains(text(), '.csv') or contains(text(), '.doc') or contains(text(), '.txt')]" # Modified existing selector
        ]
        
        attachment_elements = []
        for selector in attachment_links_selectors:
            try:
                print(f"Trying to find attachment links with selector: {selector}")
                # Use WebDriverWait to ensure elements are present
                elements = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, selector))
                )
                if elements:
                    attachment_elements.extend(elements)
                    print(f"Found {len(elements)} potential attachment(s) with selector: {selector}.")
            except TimeoutException:
                print(f"No elements found with selector: '{selector}' within timeout.")
                continue
            except NoSuchElementException:
                continue
        
        if not attachment_elements:
            print("No individual attachment links found on the page.")
            return []

        # Remove duplicate links based on href and ensure unique elements
        unique_links_map = {}
        for el in attachment_elements:
            href = el.get_attribute('href')
            if href and href not in unique_links_map:
                unique_links_map[href] = el
        
        unique_elements = list(unique_links_map.values())
        print(f"Found {len(unique_elements)} unique attachment links to process.")

        initial_files_in_dir = os.listdir(self.download_dir)
        for element in unique_elements:
            file_url = element.get_attribute('href')
            file_name = element.text.strip() or os.path.basename(urlparse(file_url).path) # Use link text as name, fallback to URL basename

            if not file_url:
                print(f"  - Skipping link with no href: {file_name}")
                continue

            print(f"  - Attempting to download: {file_name} from {file_url}")
            try:
                # Use requests to download directly if it's a direct file link
                if any(file_url.lower().endswith(ext) for ext in ['.pdf', '.docx', '.xlsx', '.pptx', '.zip', '.csv', '.txt']):
                    response = requests.get(file_url, stream=True, timeout=60)
                    response.raise_for_status() # Raise an exception for HTTP errors

                    local_file_path = os.path.join(self.download_dir, file_name)
                    # Handle duplicate filenames
                    counter = 1
                    original_file_name, file_extension = os.path.splitext(file_name)
                    while os.path.exists(local_file_path):
                        file_name = f"{original_file_name}_{counter}{file_extension}"
                        local_file_path = os.path.join(self.download_dir, file_name)
                        counter += 1

                    with open(local_file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    downloaded_files.append(local_file_path)
                    self.db_manager.add_attachment(contract_id=contract_id, file_name=file_name, file_path=local_file_path, url=file_url, download_date=time.time())
                    print(f"    - Successfully downloaded {file_name} via requests.")
                else:
                    # Fallback to Selenium click for other types or if direct download is not obvious
                    print(f"    - Attempting Selenium click for {file_name} (URL: {file_url})...")
                    # Use JavaScript click as it's often more reliable
                    self.driver.execute_script("arguments[0].click();", element)
                    
                    downloaded_file_path = self._wait_for_download_complete(initial_files_in_dir, timeout=120)

                    if downloaded_file_path:
                        downloaded_files.append(downloaded_file_path)
                        final_file_name = os.path.basename(downloaded_file_path)
                        self.db_manager.add_attachment(contract_id=contract_id, file_name=final_file_name, file_path=downloaded_file_path, url=file_url, download_date=time.time())
                        print(f"    - Successfully downloaded {final_file_name} via Selenium click.")
                        initial_files_in_dir.append(final_file_name) # Add to list to avoid re-detecting
                    else:
                        print(f"    - Selenium click failed to download file from URL: {file_url} within timeout.")
            except (RequestException, HTTPError, ElementClickInterceptedException, StaleElementReferenceException) as e:
                print(f"  - Failed to download {file_name} from {file_url}: {e}")
            except Exception as e:
                print(f"  - An unexpected error occurred downloading attachment {file_name}: {e}")

        return downloaded_files

    def _download_individual_attachments_on_crawled_page(self, contract_id, current_page_url):
        print(f"  - Attempting to download attachments on crawled page: {current_page_url} individually.")
        downloaded_files = []
        attachment_links_selectors = [
            "//a[contains(@href,'.pdf') or contains(@href,'.docx') or contains(@href,'.xlsx') or contains(@href,'.zip') or contains(@href,'.csv') or contains(@href,'.doc') or contains(@href,'.txt')]", # Broader selector
            "//a[contains(text(), '.pdf') or contains(text(), '.docx') or contains(text(), '.xlsx') or contains(text(), '.zip') or contains(text(), '.csv') or contains(text(), '.doc') or contains(text(), '.txt')]"
        ]
        
        attachment_elements = []
        for selector in attachment_links_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                if elements:
                    attachment_elements.extend(elements)
            except NoSuchElementException:
                continue
        
        if not attachment_elements:
            print("    - No individual attachment links found on the crawled page.")
            return []

        unique_links_map = {}
        for el in attachment_elements:
            href = el.get_attribute('href')
            if href and href not in unique_links_map:
                unique_links_map[href] = el
        
        unique_elements = list(unique_links_map.values())
        print(f"    - Found {len(unique_elements)} unique attachment links on crawled page to process.")

        initial_files_in_dir = os.listdir(self.download_dir)
        for element in unique_elements:
            file_url = element.get_attribute('href')
            file_name = element.text.strip() or os.path.basename(urlparse(file_url).path)

            if not file_url:
                continue

            print(f"    - Attempting Selenium click to download: {file_name} from {file_url}")
            try:
                self.driver.execute_script("arguments[0].click();", element)
                downloaded_file_path = self._wait_for_download_complete(initial_files_in_dir, timeout=120)

                if downloaded_file_path:
                    downloaded_files.append(downloaded_file_path)
                    final_file_name = os.path.basename(downloaded_file_path)
                    self.db_manager.add_attachment(contract_id=contract_id, file_name=final_file_name, file_path=downloaded_file_path, url=file_url, download_date=time.time())
                    print(f"      - Successfully downloaded {final_file_name} via Selenium click.")
                    initial_files_in_dir.append(final_file_name)
                else:
                    print(f"      - Selenium click failed to download file from URL: {file_url} within timeout.")
            except Exception as e:
                print(f"    - An error occurred downloading attachment {file_name} via Selenium click: {e}")

        return downloaded_files

    def _recursive_crawl_and_download(self, contract_id, url, depth):
        if depth == 0 or url in self.visited_urls:
            return []

        print(f"  - Crawling link (depth {depth}): {url}")
        self.visited_urls.add(url)
        downloaded_files = []
        original_window = self.driver.current_window_handle

        try:
            self.driver.execute_script("window.open(arguments[0]);", url)
            time.sleep(2)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)
            if text_content:
                file_name = f"crawled_{unquote(urlparse(url).path.split('/')[-1] or 'index')}.txt"
                file_path = os.path.join(self.download_dir, file_name)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                self.db_manager.add_attachment(contract_id=contract_id, file_name=file_name, file_path=file_path, url=url, download_date=time.time())
                downloaded_files.append(file_path)
                print(f"    - Saved text content from {url} to {file_path}")

            temp_downloaded_files = self._download_individual_attachments_on_crawled_page(contract_id, url)
            downloaded_files.extend(temp_downloaded_files)

            current_page_links = self.driver.find_elements(By.TAG_NAME, "a")
            for link_element in current_page_links:
                link_url = link_element.get_attribute('href')
                if link_url and not link_url.startswith(('mailto:', 'javascript:')):
                    next_url = urljoin(url, link_url)
                    if urlparse(next_url).netloc == urlparse(url).netloc or \
                       urlparse(next_url).netloc.endswith(f".{urlparse(url).netloc}"):
                        downloaded_files.extend(self._recursive_crawl_and_download(contract_id, next_url, depth - 1))

        except (TimeoutException, WebDriverException) as e:
            print(f"    - Could not crawl or process link {url} with Selenium: {e}")
        except Exception as e:
            print(f"    - An unexpected error occurred while processing link {url}: {e}")
        finally:
            self.driver.close()
            self.driver.switch_to.window(original_window)
        
        return downloaded_files

    def scrape_and_download(self, solicitation_url, max_retries=3, delay=5, backoff=2):
        contract_id = self._get_contract_id_from_url(solicitation_url)
        if not contract_id:
            print(f"Could not extract contract ID from URL: {solicitation_url}")
            return None, []
        
        self.visited_urls = {solicitation_url}
        details = {'contract_id': contract_id, 'url': solicitation_url}
        downloaded_files = []

        for i in range(max_retries):
            try:
                print(f"Navigating to {solicitation_url} (Attempt {i + 1}/{max_retries})")
                self.driver.get(solicitation_url)
                self._handle_cookie_banner()

                print("Attempting to scrape data...")
                details['solicitation_title'] = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//h1[contains(@class, 'card-title')]" ))).text.strip()
                description_element = self.driver.find_element(By.XPATH, "//div[@aria-describedby='desc']")
                details['description'] = description_element.text.strip()

                # --- Scrape and Crawl Links ---
                print("--- Finding and crawling links on main page ---")
                
                link_selectors = [
                    "//app-attachments[@id='attachments']//h3[text()='Links']/following-sibling::div//a",
                    "//h3[text()='Links']/following-sibling::div//a",
                    "//div[contains(@class, 'links-section')]//a",
                    "//div[@id='links']//a",
                    "//a[contains(text(), 'Link') or contains(text(), 'link')]"
                ]
                
                initial_links = []
                for selector in link_selectors:
                    try:
                        initial_links = self.driver.find_elements(By.XPATH, selector)
                        if initial_links:
                            print(f"Found {len(initial_links)} links with selector: {selector}")
                            break
                    except NoSuchElementException:
                        continue
                
                if not initial_links:
                    print("No links found with any of the selectors. Saving page source for debugging.")
                    with open(f"page_source_{contract_id}.html", "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)

                for link in initial_links:
                    link_url = link.get_attribute('href')
                    if link_url:
                        downloaded_files.extend(self._recursive_crawl_and_download(contract_id, link_url, depth=self.MAX_CRAWL_DEPTH))

                break 
            except (TimeoutException, NoSuchElementException, WebDriverException) as e:
                print(f"    - Scraping attempt {i + 1}/{max_retries} failed for {solicitation_url}: {e}")
                if i < max_retries - 1:
                    self.close()
                    self.driver = self._initialize_driver()
                    time.sleep(delay)
                    delay *= backoff
                else:
                    print(f"    - All scraping attempts failed for {solicitation_url}.")
                    self.driver.execute_script("window.stop();")
                    break

        # --- Download Attachments ---
        print("\n--- Starting attachment download process ---")
        try:
            # 1. Try to download all as a zip
            zip_files = self._download_all_attachments_as_zip(contract_id)
            if zip_files:
                downloaded_files.extend(zip_files)
                print("Successfully downloaded and extracted attachments from zip.")
            else:
                # 2. If zip fails or returns no files, try individual downloads
                print("Zip download failed or yielded no files, attempting individual downloads.")
                individual_files = self._download_individual_attachments(contract_id)
                if individual_files:
                    downloaded_files.extend(individual_files)
                    print("Successfully downloaded attachments individually.")
                else:
                    print("Individual attachment download also failed or found no files.")

        except Exception as e:
             print(f"    - An unexpected error occurred during the attachment download process: {e}")

        self.db_manager.add_solicitation(
            contract_id=contract_id,
            url=solicitation_url,
            title=details.get('solicitation_title', 'N/A'),
            description=details.get('description', 'N/A'),
            location=None, product_requirements=None, analysis_summary=None,
            data=json.dumps(details)
        )
        print(f"Saved solicitation details for {contract_id}.")
        return details, downloaded_files

    def close(self):
        if self.driver:
            self.driver.quit()
            print("WebDriver closed.")

if __name__ == "__main__":
    agent = DescriptionDownloaderAgent(headless=False)
    try:
        test_url = "https://sam.gov/workspace/contract/opp/d9b40c4f15944a31a0ddb0e970e42d62/view"
        solicitation_data, downloaded_files = agent.scrape_and_download(test_url)
        if solicitation_data:
            print("\n--- Scraped Solicitation Data ---")
            print(json.dumps(solicitation_data, indent=2))
            print("\n--- Downloaded Files ---")
            for f in downloaded_files:
                print(f)
    finally:
        agent.close()
