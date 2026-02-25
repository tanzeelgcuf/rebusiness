
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

from proxy_manager import ProxiflyManager

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
                self.model = genai.GenerativeModel('gemini-2.5-flash-image') # Migrated for higher quota
            except Exception as e:
                print(f"Warning: Gemini import failed: {e}")
    
    def select_vendors_and_submit_rfq(self, product, limit=5, attachment_file_path=None):
        """
        NEW WORKFLOW: Use ThomasNet's Internal RFQ System.
        1. Search for product
        2. Select N vendors via individual "Select" buttons
        3. Click "Request Quote" button in bottom selection div
        4. Fill ThomasNet's RFQ form (subject, message, attachment)
        5. Check verification checkbox
        6. Submit via "Send Request" button
        
        Args:
            product: dict with product_name, quantity, due_date, etc.
            limit: number of vendors to select (default 5)
            attachment_file_path: path to .docx RFQ file to attach (optional)
        
        Returns: dict with 'success', 'vendors_contacted', 'confirmation_message'
        """
        product_name = product.get('product_name', 'Product')
        product_details = product  # Full product dict with notice_id, quantity, etc.
        
        print(f"\n=== ThomasNet Internal RFQ for: {product_name} ===")
        
        result = {
            'success': False,
            'vendors_contacted': 0,
            'confirmation_message': None,
            'error': None
        }
        
        try:
            with sync_playwright() as p:
                # STEALTH MODE: Connect to already-running Chrome with remote debugging
                print("  Connecting to Chrome via CDP (Remote Debugging)...")
                try:
                    browser = p.chromium.connect_over_cdp("http://localhost:9222")
                    context = browser.contexts[0] if browser.contexts else None
                    if not context:
                        print("  ERROR: No browser context found. Please ensure Chrome is running with remote debugging.")
                        print("  Run: python3 setup_chrome_debugging.py for instructions.")
                        result['error'] = "Chrome remote debugging not enabled"
                        return result
                    page = context.pages[0] if context.pages else context.new_page()
                except Exception as cdp_error:
                    print(f"  CDP connection failed: {cdp_error}")
                    print("  Falling back to regular Chrome launch...")
                    
                    # Fetch proxy if available
                    pm = ProxiflyManager(test_url="https://www.thomasnet.com", timeout=8)
                    proxy_config = pm.get_working_proxy(protocols=['http', 'socks5'], us_only=True)
                    if not proxy_config:
                        print("  Warning: No working proxy found, proceeding without proxy.")
                    else:
                        print(f"  Using proxy: {proxy_config['server']}")

                    # Fallback: regular launch without persistent context
                    browser = p.chromium.launch(
                        headless=False,
                        channel="chrome",
                        args=['--disable-blink-features=AutomationControlled'],
                        proxy=proxy_config
                    )
                    context = browser.new_context(
                        viewport={'width': 1366, 'height': 768}
                    )
                    page = context.new_page()
                
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # STEP 1: Navigate and Search (reuse existing logic)
                print("Step 1: Navigating to ThomasNet...")
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        page.goto("https://www.thomasnet.com/suppliers", timeout=60000, wait_until="networkidle")
                        break
                    except Exception as e:
                        print(f"  Navigation attempt {attempt+1} failed: {e}")
                        time.sleep(2)
                        if attempt == max_retries - 1:
                            raise e
                
                page.wait_for_load_state("domcontentloaded")
                time.sleep(3)
                
                # Dismiss cookie banner
                try:
                    if page.is_visible('#gdpr-btn-accept'):
                        page.click('#gdpr-btn-accept')
                        time.sleep(1)
                except: pass
                
                # Search
                print(f"Step 2: Searching for '{product_name}'...")
                search_input = 'input[data-ref="srp.DiscoverBox.input"]'
                try:
                    page.wait_for_selector(search_input, state='visible', timeout=10000)
                    page.click(search_input)
                    page.fill(search_input, product_name)
                    page.press(search_input, "Enter")
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception as e:
                    print(f"  Search failed, using direct URL: {e}")
                    term = product_name.replace(' ', '+')
                    url = f"https://www.thomasnet.com/suppliers/search?searchterm={term}&search_type=search-supplier"
                    page.goto(url, timeout=60000, wait_until="networkidle")
                
                # CAPTCHA handling
                time.sleep(2)
                if "Access blocked" in page.title() or "captcha" in page.content().lower():
                    print("  ⚠️  CAPTCHA detected! Please solve it in the browser.")
                    print("  Waiting up to 120 seconds...")
                    try:
                        page.wait_for_function("""
                            () => {
                                const selectors = [
                                    'li[data-sentry-component="SearchResultSupplier"]',
                                    'div.search-result-supplier',
                                    'input[type="checkbox"]'
                                ];
                                return selectors.some(s => document.querySelector(s));
                            }
                        """, timeout=120000)
                        print("  ✓ Access restored!")
                    except:
                        result['error'] = "CAPTCHA timeout"
                        try:
                            if hasattr(browser, 'close'): browser.close()
                        except: pass
                        return result
                
                # STEP 3: Select Vendors (NEW LOGIC)
                print(f"Step 3: Selecting {limit} vendors...")
                time.sleep(2)  # Let page settle
                
                # Find checkboxes - Try multiple patterns
                # STEP 3: Select top 5 vendors (click individual "Select" buttons)
                print("Step 3: Selecting top 5 vendors...")
                
                # Wait for search results to load
                time.sleep(5)
                page.wait_for_load_state("networkidle", timeout=30000)
                
                # Try different selectors for individual "Select" buttons on vendor cards
                select_button_selectors = [
                    'button:has-text("Select")',
                    'button[data-ref*="select"]',
                    'button[aria-label*="Select"]',
                    'a:has-text("Select")',
                    '[role="button"]:has-text("Select")'
                ]
                
                select_buttons = []
                for sel in select_button_selectors:
                    select_buttons = page.query_selector_all(sel)
                    if len(select_buttons) > 0:
                        print(f"  Found {len(select_buttons)} Select buttons using selector: {sel}")
                        break
                
                if len(select_buttons) == 0:
                    result['error'] = "No vendor Select buttons found"
                    try:
                        if hasattr(browser, 'close'): browser.close()
                    except: pass
                    return result
                
                # Click "Select" button for top 5 vendors
                selected_count = 0
                for i, btn in enumerate(select_buttons[:5]):
                    try:
                        btn.click(timeout=3000)
                        selected_count += 1
                        print(f"  ✓ Selected vendor {i+1}")
                        time.sleep(1)  # Wait for selection to register
                    except Exception as e:
                        print(f"  ⚠ Failed to select vendor {i+1}: {e}")
                
                if selected_count == 0:
                    result['error'] = "Failed to select any vendors"
                    try:
                        if hasattr(browser, 'close'): browser.close()
                    except: pass
                    return result
                
                print(f"Selected {selected_count} vendors")
                time.sleep(5)  # Increased wait time for bottom selection div to appear
                
                # STEP 4: Click "Send Request" button in bottom selection div
                print("Step 4: Clicking 'Send Request' button in bottom selection div...")
                
                # Based on actual HTML, the button text is "Send Request" not "Request Quote"
                request_quote_selectors = [
                    'button:has-text("Send Request")',
                    'button:has-text("Send")',
                    'button:has-text("Request Quote")',
                    'button:has-text("Request")',
                    'a:has-text("Send Request")',
                    'button[type="submit"]',
                    'button[data-ref*="request"]',
                    'button[data-ref*="send"]',
                    '[role="button"]:has-text("Send")'
                ]
                
                clicked = False
                for sel in request_quote_selectors:
                    try:
                        btn = page.query_selector(sel)
                        if btn and btn.is_visible():
                            btn.click(timeout=5000)
                            clicked = True
                            print(f"  ✓ Clicked button using selector: {sel}")
                            break
                    except: pass
                
                if not clicked:
                    result['error'] = "Request Quote button not found in bottom selection div"
                    try:
                        if hasattr(browser, 'close'): browser.close()
                    except: pass
                    return result
                
                # Wait for RFQ form to appear
                time.sleep(3)
                page.wait_for_load_state("networkidle", timeout=10000)
                
                # STEP 5: Fill RFQ Form
                print("Step 5: Filling RFQ form...")
                
                # Import identity
                from ai_agents.OutreachAgent.form_filler import IDENTITY
                
                # Common field mappings (heuristic)
                form_fields = {
                    'subject': ['input[name*="subject"]', 'input[id*="subject"]', 'input[placeholder*="Subject"]'],
                    'name': ['input[name*="name"]', 'input[id*="name"]', 'input[placeholder*="Name"]'],
                    'email': ['input[type="email"]', 'input[name*="email"]', 'input[id*="email"]'],
                    'phone': ['input[type="tel"]', 'input[name*="phone"]', 'input[id*="phone"]'],
                    'company': ['input[name*="company"]', 'input[id*="company"]'],
                    'message': ['textarea', 'textarea[name*="message"]', 'textarea[id*="comment"]', 'textarea[name*="detail"]']
                }
                
                def fill_field(field_name, value, selectors_list):
                    for sel in selectors_list:
                        try:
                            field = page.query_selector(sel)
                            if field and field.is_visible():
                                field.fill(value)
                                print(f"  ✓ Filled {field_name}")
                                return True
                        except: pass
                    print(f"  ⚠ Could not find field: {field_name}")
                    return False
                
                # Fill form - Subject first
                fill_field('subject', 'Request for Quote', form_fields['subject'])
                fill_field('name', IDENTITY['FULL_NAME'], form_fields['name'])
                fill_field('email', IDENTITY['EMAIL'], form_fields['email'])
                fill_field('phone', IDENTITY['PHONE'], form_fields['phone'])
                fill_field('company', IDENTITY['COMPANY'], form_fields['company'])
                
                # Generate message
                message = f"""Request for Quote - {product_name}

Product/Service Required: {product_name}
Quantity: {product_details.get('quantity', 'To be determined')}
Delivery Timeline: {product_details.get('due_date', 'ASAP')}

We are evaluating suppliers for this requirement. Please provide:
- Itemized pricing
- Lead time
- Warranty information

Contact: {IDENTITY['EMAIL']}
"""
                fill_field('message', message, form_fields['message'])
                
                # STEP 5.5: Upload attachment (if provided)
                if attachment_file_path:
                    print(f"Step 5.5: Uploading attachment: {attachment_file_path}...")
                    import os
                    if not os.path.exists(attachment_file_path):
                        print(f"  ⚠ Warning: Attachment file not found: {attachment_file_path}")
                    else:
                        # Try to find file input
                        file_input_selectors = [
                            'input[type="file"]',
                            'input[accept*="document"]',
                            'input[name*="file"]',
                            'input[name*="attachment"]',
                            'input[id*="file"]'
                        ]
                        
                        file_uploaded = False
                        for sel in file_input_selectors:
                            try:
                                file_input = page.query_selector(sel)
                                if file_input:
                                    # Set the file on the input element
                                    file_input.set_input_files(attachment_file_path)
                                    print(f"  ✓ Uploaded attachment: {os.path.basename(attachment_file_path)}")
                                    file_uploaded = True
                                    time.sleep(2)  # Wait for upload to process
                                    break
                            except Exception as e:
                                print(f"  ⚠ Failed to upload with selector {sel}: {e}")
                        
                        if not file_uploaded:
                            print(f"  ⚠ Warning: Could not find file upload input. Attachment not uploaded.")
                else:
                    print("Step 5.5: No attachment provided (skipping)")
                
                # STEP 6: Check the verification checkbox
                print("Step 6: Checking verification checkbox...")
                checkbox_selectors = [
                    'input[type="checkbox"]',
                    'input[type="checkbox"][id*="verify"]',
                    'input[type="checkbox"][name*="verify"]',
                    'input[type="checkbox"] + label:has-text("verify")'
                ]
                
                checkbox_found = False
                for sel in checkbox_selectors:
                    try:
                        checkbox = page.query_selector(sel)
                        if checkbox and checkbox.is_visible():
                            if not checkbox.is_checked():
                                checkbox.click()
                                print("  ✓ Checked verification checkbox")
                            else:
                                print("  ✓ Verification checkbox already checked")
                            checkbox_found = True
                            break
                    except: pass
                
                if not checkbox_found:
                    print("  ℹ Verification checkbox not found (may not be required)")
                
                # STEP 7: Submit
                print("Step 7: Submitting form...")
                time.sleep(2)  # Let user verify before submit
                
                # Based on user screenshot, the button is blue "Send Request" on the right side
                submit_selectors = [
                    'button:has-text("Send Request")',  # Most likely
                    'button[type="submit"]:has-text("Send")',
                    'button.btn-primary:has-text("Send")',  # Blue button class
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:has-text("Send")',
                    'button:has-text("Submit")'
                ]
                
                submitted = False
                for sel in submit_selectors:
                    try:
                        btn = page.query_selector(sel)
                        if btn and btn.is_visible():
                            # Get button text for confirmation
                            btn_text = btn.text_content() or btn.get_attribute('value') or 'Submit'
                            btn.click()
                            submitted = True
                            print(f"  ✓ Clicked '{btn_text.strip()}' button")
                            break
                    except Exception as e:
                        pass  # Try next selector
                
                if not submitted:
                    print("  WARNING: Could not find submit button. Please submit manually.")
                    result['error'] = "Submit button not found (manual action required)"
                else:
                    time.sleep(3)
                    # Check for confirmation
                    content = page.content().lower()
                    if "thank" in content or "success" in content or "sent" in content:
                        result['success'] = True
                        result['confirmation_message'] = "RFQ submitted successfully"
                    else:
                        result['success'] = True  # Assume success if no error
                        result['confirmation_message'] = "Form submitted (confirmation not detected)"
                
                result['vendors_contacted'] = selected_count
                
                # ===== LOG TO DASHBOARD DATABASE =====
                if result['success'] and selected_count > 0:
                    try:
                        # Extract contract_id from product dict or attachment path
                        contract_id = product_details.get('contract_id') or product_details.get('notice_id', 'unknown')
                        if contract_id == 'unknown' and attachment_file_path:
                            # Try to extract from filename
                            import os
                            filename = os.path.basename(attachment_file_path)
                            if '_RFQ_' in filename:
                                contract_id = filename.split('_RFQ_')[0]
                        
                        # Log each vendor submission to dashboard database
                        print(f"\n📊 Logging {selected_count} vendor submissions to dashboard...")
                        for i in range(selected_count):
                            self.db.add_thomasnet_submission(
                                contract_id=contract_id,
                                vendor_name=f"Vendor {i+1}",  # Placeholder - actual vendor names not easily extracted
                                vendor_company=f"ThomasNet Supplier {i+1}",
                                vendor_location="Unknown",  # Would need to scrape from results
                                product_searched=product_name,
                                rfq_file_path=attachment_file_path or "",
                                success=True,
                                error_message=None
                            )
                        print(f"  ✅ Logged {selected_count} submissions to dashboard database")
                    except Exception as log_error:
                        print(f"  ⚠️  Dashboard logging failed (non-critical): {log_error}")
                
                # Keep browser open for 5s for user to see result
                print("\nKeeping browser open for 5 seconds...")
                time.sleep(5)
                # Don't close if using CDP (connected to existing Chrome)
                try:
                    if hasattr(browser, 'close'):
                        browser.close()
                except: pass
                
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
            result['error'] = str(e)
        
        return result
    
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
                
                # Fetch proxy if available
                pm = ProxiflyManager(test_url="https://www.thomasnet.com", timeout=8)
                proxy_config = pm.get_working_proxy(protocols=['http', 'socks5'], us_only=True)
                if not proxy_config:
                    print("  Warning: No working proxy found, proceeding without proxy.")
                else:
                     print(f"  Using proxy: {proxy_config['server']}")

                # Launch options - Use regular Firefox launch (not persistent context)
                browser = p.firefox.launch(
                    headless=False,  # Show browser for manual login
                    args=['--disable-blink-features=AutomationControlled'],
                    proxy=proxy_config
                )
                
                browser_context = browser.new_context(
                    viewport={'width': 1366, 'height': 768},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
                )
                
                page = browser_context.new_page()
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # Search via Suppliers Page (Interactive)
                print(f"  Navigating to Search Page: https://www.thomasnet.com/suppliers")
                
                # Retry logic for initial navigation
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        page.goto("https://www.thomasnet.com/suppliers", timeout=60000, wait_until="networkidle")
                        break
                    except Exception as e:
                        print(f"  Navigation attempt {attempt+1} failed: {e}")
                        time.sleep(2)
                        if attempt == max_retries - 1:
                            raise e
                            
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
                        # Wait for ANY of the valid result indicators
                        page.wait_for_function("""
                            () => {
                                const selectors = [
                                    'li[data-sentry-component="SearchResultSupplier"]',
                                    'div.search-result-supplier', 
                                    'div.supplier-card',
                                    'li.search-list__item',
                                    'div[data-testid="supplier-card"]'
                                ];
                                return selectors.some(s => document.querySelector(s));
                            }
                        """, timeout=120000)
                        print("  Success! Access restored.")
                    except:
                        print("  Timed out waiting for manual CAPTCHA solution (or no results appeared).")
                
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
                    
                    # Try multiple selectors for robustness
                    selectors = [
                        'li[data-sentry-component="SearchResultSupplier"]',
                        'div.search-result-supplier', 
                        'div.supplier-card',
                        'li.search-list__item',
                        'div[data-testid="supplier-card"]'
                    ]
                    
                    items = []
                    for sel in selectors:
                        items = soup.select(sel)
                        if items:
                            print(f"  Found {len(items)} items using selector: {sel}")
                            break
                            
                    if not items:
                        print("  WARNING: No items found with any selector!")
                        # Debug dump
                        print(f"  Page Title: {page.title()}")
                        print(f"  HTML Preview: {html_content[:500]}...")
                        # Try to find *any* useful structure
                        if "captcha" in html_content.lower():
                            print("  DEBUG: CAPTCHA still present in HTML source.")
                        
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

                            # Extract description snippet for validation
                            description = ""
                            desc_el = item.select_one('[data-sentry-component="TrimmedDescription"]')
                            if desc_el:
                                description = desc_el.get_text(strip=True)

                            if name: 
                                # Deduplicate
                                if not any(s['name'] == name for s in suppliers):
                                    suppliers.append({
                                        'name': name,
                                        'website': website,
                                        'description': description,
                                        'email': None, 
                                        'phone': None, 
                                        'location': None 
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
                browser.close()
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

    def _enrich_supplier_details(self, company_name, product_context, known_website=None):
        """
        [DEEP CRAWL UPGRADE]
        Finds company website via DuckDuckGo (or uses known_website), then VISITS the site to extract emails/forms.
        """
        print(f"  Enriching details for: {company_name} (Deep Crawl Mode)...")
        try:
            website_url = known_website
            best_match = None # Initialize to avoid UnboundLocalError
            
            if not website_url:
                from duckduckgo_search import DDGS
                query = f"{company_name} official site contact email"
                # Limit results to find the best match
                try:
                    results = DDGS().text(query, region='us-en', max_results=3)
                except Exception as e:
                    print(f"    > Search Engine Error: {e}")
                    return None
                
                ignored_domains = [
                    'youtube.com', 'facebook.com', 'linkedin.com', 'twitter.com', 
                    'instagram.com', 'pinterest.com', 'thomasnet.com', 'zoominfo.com',
                    'dnb.com', 'manta.com', 'bbb.org', 'mapquest.com', 'yellowpages.com'
                ]
                
                best_match = None
                
                for res in results:
                    href = res['href']
                    domain = urlparse(href).netloc.lower()
                    
                    if any(ignored in domain for ignored in ignored_domains):
                        continue
                        
                    best_match = res
                    break
                
                if not best_match:
                    print(f"  Could not find official site for {company_name}")
                    return None

                website_url = best_match['href']

            print(f"  Visiting Official Site: {website_url}")
            print(f"  Visiting Official Site: {website_url}")
            
            # --- DEEP CRAWL (Playwright) ---
            crawled_email = None
            has_contact_form = False
            
            try:
                # Use context from main thread if possible, or new ephemeral one
                with sync_playwright() as p:
                    # Headless for background execution
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                        viewport={'width': 1280, 'height': 720}
                    )
                    page = context.new_page()
                    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    
                    try:
                        page.goto(website_url, timeout=30000, wait_until="domcontentloaded")
                        
                        # 1. Scrape Homepage & Footer
                        # Scroll to bottom to trigger lazy loading / footer
                        try:
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(2)
                        except: pass
                        
                        content = page.content()
                        crawled_email = self._extract_email(content)
                        
                        # Check for form signals
                        if "contact" in content.lower() or "form" in content.lower():
                            if page.locator("form").count() > 0:
                                has_contact_form = True
                                
                        # 2. Visit "Contact" Page (if email not found or just to be thorough)
                        if not crawled_email:
                            # Try robust selector for Contact links
                            contact_link = None
                            try:
                                # Look for 'a' tags containing 'contact' in href or text
                                contact_link = page.locator("a[href*='contact']").first
                                if not contact_link.is_visible():
                                    contact_link = page.get_by_text("Contact Us", exact=False).first
                                if not contact_link.is_visible():
                                    contact_link = page.get_by_text("Contact", exact=True).first
                            except: pass

                            if contact_link and contact_link.count() > 0 and contact_link.is_visible():
                                print("    > navigating to Contact page (checking footer/page)...")
                                try:
                                    contact_link.click(timeout=5000)
                                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                                    
                                    # Scroll contact page too
                                    try:
                                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                        time.sleep(2)
                                    except: pass
                                    
                                    content = page.content()
                                    crawled_email = self._extract_email(content)
                                    if page.locator("form").count() > 0:
                                         has_contact_form = True
                                except Exception as e:
                                    print(f"    > Contact page nav failed: {e}")
                                     
                    except Exception as e:
                        print(f"    > Crawl warning: {e}")
                    finally:
                        browser.close()
            except Exception as e:
                print(f"    > Playwright error: {e}")

            # Fallback to snippet extract if crawl failed
            if not crawled_email and best_match:
                crawled_email = self._extract_email(best_match['body'])
            
            return {
                'name': company_name,
                'website': website_url,
                'email': crawled_email,
                'phone': self._extract_phone(best_match['body']) if best_match else None, 
                'source': 'ThomasNet + Deep Crawl',
                'has_form': has_contact_form,
                'notes': f"Deep Crawl: Email={crawled_email}, Form={has_contact_form}"
            }

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
