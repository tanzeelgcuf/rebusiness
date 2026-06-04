import logging
import time
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

import yaml

logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent / "config.yaml"
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r") as f:
        CONFIG = yaml.safe_load(f)


def solve_slider_if_present(page, auth=None) -> bool:
    """
    Detect and solve DataDome slider captcha using CapSolver/2Captcha.
    Returns True if no captcha or successfully solved, False if failed.

    Args:
        page: Playwright Page object
        auth: Optional ThomasNetAuth instance (if available)
    """
    # Quick check — no DataDome iframe? nothing to do.
    from captcha_solver import detect_datadome
    if not detect_datadome(page):
        return True

    logger.warning("⚠️  DataDome slider detected — attempting automated solve...")

    # If auth object with solver exists, use it
    if auth and hasattr(auth, 'bypass_captcha'):
        return auth.bypass_captcha(retries=3)

    # Fallback: use standalone solver
    from captcha_solver import DataDomeSolver
    api_key = os.getenv("TWO_CAPTCHA_API_KEY")
    cap_key = os.getenv("CAPSOLVER_API_KEY")
    if not api_key and cap_key and cap_key != "your_capsolver_key_here":
        solver = DataDomeSolver()
    elif api_key:
        solver = DataDomeSolver(api_key)
    else:
        logger.error("No captcha solver configured — set TWO_CAPTCHA_API_KEY or CAPSOLVER_API_KEY")
        return False

    try:
        ua = page.evaluate("navigator.userAgent")
        token = solver.solve_datadome(page.url, ua)
        logger.info("Adding solved datadome cookie...")
        page.context.add_cookies([{
            'name': 'datadome',
            'value': token,
            'domain': '.thomasnet.com',
            'path': '/'
        }])
        page.reload(wait_until="domcontentloaded")
        time.sleep(3)
        if detect_datadome(page):
            logger.error("DataDome still present after solve.")
            return False
        logger.info("✅ DataDome slider solved successfully!")
        return True
    except Exception as e:
        logger.error(f"Slider solve failed: {e}")
        return False

class RFQFormFiller:
    """
    Handles filling and submitting RFQ forms on ThomasNet vendor pages.
    """
    
    def __init__(self, auth: Any, config: Dict = None):
        # Accept either an auth object (with .page) or a direct Page
        if hasattr(auth, 'page'):
            self.auth = auth
            self.page = auth.page
        else:
            self.auth = None
            self.page = auth  # caller passed a Page directly
        self.config = config or CONFIG
        self.company_info = self.config.get("company", {})
        
    def submit_rfq(self, vendor: Dict[str, Any], summary: str, rfq_file_path: str, contact_info: Dict = None) -> Dict[str, Any]:
        """
        Navigate to vendor page and submit RFQ.
        
        Args:
            vendor: Vendor dict from search results
            summary: Generated RFQ summary text
            rfq_file_path: Path to RFQ document to attach
            contact_info: Optional override for contact details
            
        Returns:
            Dict with success status and confirmation details
        """
        vendor_name = vendor.get("name", "Unknown Vendor")
        profile_url = vendor.get("profile_url")
        
        if not profile_url:
            return {
                'success': False,
                'vendor_name': vendor_name, 
                'error': "No profile URL found"
            }
            
        logger.info(f"Submitting RFQ to {vendor_name}...")
        
        try:
            # 1. Navigate to Vendor Profile
            self.page.goto(profile_url)
            
            # Check for DataDome immediately after navigation
            if self.auth and hasattr(self.auth, 'bypass_captcha'):
                self.auth.bypass_captcha()
            else:
                solve_slider_if_present(self.page)

            # 2. Find "Contact" or "Quote" button
            # Selectors based on likely ThomasNet buttons
            action_buttons = [
                'a[href*="/contact"]', 
                'a:has-text("Contact Supplier")', 
                'button:has-text("Request Quote")',
                'a.primary-button'
            ]
            
            clicked = False
            for selector in action_buttons:
                try:
                    if self.page.locator(selector).first.is_visible():
                        self.page.locator(selector).first.click()
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                # If no button found, check if form is already on page (embedded)
                if not self.page.locator('form').count() > 0:
                     return {
                        'success': False,
                        'vendor_name': vendor_name,
                        'error': "Could not find contact button or form"
                    }
            
            # Wait for form to load
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=15000)
                # Additional wait for actual form fields
                self.page.wait_for_selector('form, input, textarea', timeout=10000)
            except:
                logger.warning("Brief timeout waiting for form to load, proceeding anyway...")
            
            # 3. Fill Form Fields
            info = contact_info or self.company_info
            
            # Contact Info
            self._fill_contact_info(info)
            
            # Summary / Message
            self._fill_summary(summary)
            
            # 4. Attach File
            if rfq_file_path:
                self._attach_file(rfq_file_path)
            
            # 5. Submit
            submit_buttons = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Send Message")',
                'button:has-text("Submit Request")'
            ]
            
            submitted = False
            for btn in submit_buttons:
                if self.page.locator(btn).first.is_visible():
                     self.page.locator(btn).first.click()
                     submitted = True
                     break
                     
            if not submitted:
                 # Take screenshot
                debug_path = Path("logs") / f"submit_error_{int(time.time())}.png"
                debug_path.parent.mkdir(exist_ok=True)
                self.page.screenshot(path=debug_path)
                return {
                    'success': False,
                    'vendor_name': vendor_name,
                    'error': "Could not find submit button"
                }
                
            # 6. Wait for Confirmation
            # Look for success message or navigation
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=15000)
            except:
                pass
            
            # Check for confirmation indicators
            confirmation = self._get_confirmation()
            
            return {
                'success': True,
                'vendor_name': vendor_name,
                'confirmation_number': confirmation
            }
            
        except Exception as e:
            # Capture error state
            try:
                debug_path = Path("logs") / f"error_{int(time.time())}.png"
                debug_path.parent.mkdir(exist_ok=True)
                self.page.screenshot(path=debug_path)
            except:
                pass
                
            logger.error(f"Submission error for {vendor_name}: {e}")
            return {
                'success': False,
                'vendor_name': vendor_name,
                'confirmation_number': None,
                'error': str(e)
            }
    
    def _fill_contact_info(self, contact_info: Dict):
        """Fill contact information fields"""
        field_mappings = {
            'company_name': ['input[name*="company"]', 'input#company'],
            'contact_name': ['input[name*="name"]', 'input#contact-name'],
            'email': ['input[type="email"]', 'input[name*="email"]'],
            'phone': ['input[type="tel"]', 'input[name*="phone"]'],
            'address': ['input[name*="address"]', 'textarea[name*="address"]'],
        }
        
        for field, selectors in field_mappings.items():
            value = contact_info.get(field)
            if not value:
                continue
            
            for selector in selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.is_visible():
                        element.fill(str(value))
                        break
                except:
                    continue
    
    def _fill_summary(self, summary: str):
        """Fill the main RFQ description/summary field"""
        summary_selectors = [
            'textarea[name*="description"]',
            'textarea[name*="message"]',
            'textarea[name*="details"]',
            'textarea#rfq-details',
            'textarea.rfq-message'
        ]
        
        for selector in summary_selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible():
                    element.fill(summary)
                    logger.info(f"Filled summary ({len(summary)} chars)")
                    return
            except:
                continue
        
        logger.warning("Could not find summary field")
    
    def _attach_file(self, file_path: str):
        """Attach RFQ document file"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return
        
        file_input_selectors = [
            'input[type="file"]',
            'input[name*="attachment"]',
            'input[name*="document"]',
            '#file-upload'
        ]
        
        for selector in file_input_selectors:
            try:
                file_input = self.page.locator(selector).first
                if file_input.count() > 0:
                    file_input.set_input_files(str(file_path))
                    logger.info(f"Attached file: {file_path.name}")
                    return
            except:
                continue
        
        logger.warning("Could not find file upload field")
    
    def _get_confirmation(self) -> str:
        """Extract confirmation number/message after submission"""
        confirmation_selectors = [
            '.confirmation-message',
            '.success-message',
            '#confirmation-number',
            'div:has-text("RFQ-")',
            'p:has-text("confirmation")'
        ]
        
        for selector in confirmation_selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible():
                    return element.inner_text().strip()
            except:
                continue
        
        return "Submitted (no confirmation number found)"

    def _ensure_auth_page(self):
        """Ensure auth has a valid page; attempt login if not."""
        if not self.page:
            from auth import ThomasNetAuth
            if not isinstance(self.auth, ThomasNetAuth):
                raise RuntimeError("No valid page and auth is not ThomasNetAuth")
            if not self.auth.page:
                self.auth.start_browser()
                self.auth.login()
                self.page = self.auth.page

    def submit_multi_vendor_rfq(self, product_name: str, vendors: List[str],
                                summary: str, rfq_file_path: str) -> Dict[str, Any]:
        """
        Submit RFQ to multiple vendors using ThomasNet's batch selection system.
        
        This method assumes we're already on the search results page.
        
        Workflow:
        1. Click "Select" button for each vendor
        2. Click "Request Quote" button (appears after selections)
        3. Fill the RFQ form:
           - Subject: "Request for Quote"
           - Details: summary (100 chars max)
           - Attachment: RFQ document
           - Verify checkbox
        4. Click "Send Request"
        
        Args:
            product_name: Name of the product being quoted
            vendors: List of vendor names to select
            summary: RFQ summary/description (will be truncated to 100 chars)
            rfq_file_path: Path to RFQ document to attach
            
        Returns:
            Dict with success status and results
        """
        try:
            logger.info(f"Starting multi-vendor RFQ submission for {len(vendors)} vendors")

            # Ensure page is available
            self._ensure_auth_page()

            # --- Slider verification before submission ---
            if not solve_slider_if_present(self.page, self.auth):
                logger.warning("DataDome slider present and not solved — submission may fail")

            # Step 1: Select vendors by clicking "Select" button on each card
            selected_count = 0
            for vendor_name in vendors:
                try:
                    # Find the vendor card by looking for h2 containing the vendor name
                    # Then find the Select button within that card's parent li element
                    vendor_card = self.page.locator(f'li:has(h2:has-text("{vendor_name}"))').first
                    
                    if vendor_card.count() > 0:
                        select_btn = vendor_card.locator('button:has-text("Select")').first
                        if select_btn.count() > 0 and select_btn.is_visible():
                            select_btn.click()
                            selected_count += 1
                            logger.info(f"✓ Selected vendor {selected_count}/{len(vendors)}: {vendor_name}")
                            
                            # CONFIRMATION LOG FOR USER
                            logger.info(f"CONFIRMATION: Selected Vendor '{vendor_name}' for Product '{product_name}'")
                            
                            time.sleep(2)  # Human-like delay between vendor selections
                        else:
                           logger.warning(f"Select button not found or not visible for {vendor_name}")
                    else:
                        logger.warning(f"Vendor card not found for {vendor_name}")
                        
                except Exception as e:
                    logger.error(f"Error selecting vendor {vendor_name}: {e}")
                    continue
            
            if selected_count == 0:
                return {
                    'success': False,
                    'error': 'No vendors were selected',
                    'vendors_contacted': 0
                }
            
            logger.info(f"Selected {selected_count} vendors successfully")
            time.sleep(5)  # Human-like delay to "review" selections before continuing
            
            # Step 2: Click "Request Quote" button
            # This button appears after selecting vendors, usually at top or bottom of page
            try:
                # Wait for any "Request Quote" button to appear
                # The button might say "Request Quote" or "Request a Quote"
                logger.info("Waiting for Request Quote button...")
                
                # Check for floating action button or bottom bar button
                quote_btn_selectors = [
                    'button:has-text("Request Quote")',
                    'a:has-text("Request Quote")',
                    'button:has-text("Request a Quote")',
                    'a:has-text("Request a Quote")',
                    'button.batch-rfq-trigger',
                    'a.batch-rfq-trigger',
                    '[data-testid="request-quote-button"]'
                ]
                
                request_quote_btn = None
                for selector in quote_btn_selectors:
                    try:
                        btn = self.page.locator(selector).first
                        if btn.is_visible():
                            request_quote_btn = btn
                            break
                    except:
                        continue
                
                if request_quote_btn:
                    # Scroll into view if needed
                    request_quote_btn.scroll_into_view_if_needed()
                    time.sleep(1)
                    request_quote_btn.click()
                    logger.info("✓ Clicked Request Quote button")
                    time.sleep(5)  # Human-like delay - wait for form to fully load
                else:
                    logger.warning("Request Quote button not found immediately. Waiting...")
                    # Try waiting for the primary selector
                    try:
                        self.page.wait_for_selector('button:has-text("Request Quote")', timeout=5000)
                        self.page.locator('button:has-text("Request Quote")').first.click()
                        logger.info("✓ Clicked Request Quote button (after wait)")
                        time.sleep(5)
                    except:
                        # Debug: Dump HTML to see why button is missing
                        try:
                            Path("logs").mkdir(exist_ok=True)
                            with open("logs/missing_quote_button.html", "w", encoding="utf-8") as f:
                                f.write(self.page.content())
                            self.page.screenshot(path="logs/missing_quote_button.png")
                            logger.info("Saved debug info to logs/missing_quote_button.html and .png")
                        except Exception as dump_err:
                            logger.error(f"Failed to save debug info: {dump_err}")
                            
                        return {
                            'success': False,
                            'error': 'Request Quote button not found after selecting vendors. HTML dumped to logs.',
                            'vendors_contacted': 0
                        }
            except Exception as e:
                logger.error(f"Error clicking Request Quote button: {e}")
                return {
                    'success': False,
                    'error': f'Failed to click Request Quote: {str(e)}',
                    'vendors_contacted': 0
                }
            
            # Step 3: Fill the RFQ form
            try:
                # Wait for form to be visible
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    self.page.wait_for_selector('input[name*="subject"], textarea', timeout=10000)
                except:
                    pass
                
                # CONFIRMATION LOGS FOR USER
                logger.info("="*50)
                logger.info(f"CONFIRMATION: Filling RFQ Form")
                logger.info(f"CONFIRMATION: Product: {product_name}")
                logger.info(f"CONFIRMATION: Attaching File: {rfq_file_path}")
                logger.info("="*50)
                
                # Fill Subject field
                subject_field = self.page.locator('input[name*="subject"], input[id*="subject"]').first
                if subject_field.is_visible():
                    subject_field.click()
                    time.sleep(1)
                    subject_field.type("Request for Quote", delay=100)  # Type like a human
                    logger.info("✓ Filled subject field")
                    time.sleep(2)  # Pause after filling subject
                
                # Fill Details/Question field
                details_field = self.page.locator(
                    'textarea[name*="details"], textarea[name*="question"], textarea[name*="message"]'
                ).first
                if details_field.is_visible():
                    # Truncate summary to 100 characters
                    truncated_summary = summary[:100]
                    details_field.click()
                    time.sleep(1)
                    details_field.type(truncated_summary, delay=80)  # Type details slowly
                    logger.info(f"✓ Filled details field ({len(truncated_summary)} chars)")
                    time.sleep(3)  # Pause after typing details
                
                # Attach file
                file_input = self.page.locator('input[type="file"]').first
                if file_input.count() > 0 and rfq_file_path:
                    file_path = Path(rfq_file_path)
                    if file_path.exists() and file_path.is_file():
                        file_input.set_input_files(str(file_path))
                        logger.info(f"✓ Attached file: {file_path.name}")
                        time.sleep(3)  # Delay after file upload
                    else:
                        logger.warning(f"File not found or not a file: {rfq_file_path}")
                elif file_input.count() > 0:
                    logger.info("Skipping file upload — no file path provided")
                
                # Check verification checkbox
                verify_checkbox = self.page.locator('input[type="checkbox"]').first
                if verify_checkbox.is_visible():
                    time.sleep(2)  # Pause before checking box
                    verify_checkbox.check()
                    logger.info("✓ Checked verification checkbox")
                
                time.sleep(5)  # Final review pause before submission
                
            except Exception as e:
                logger.error(f"Error filling form: {e}")
                # Take screenshot for debugging
                try:
                    debug_path = Path("logs") / f"form_fill_error_{int(time.time())}.png"
                    debug_path.parent.mkdir(exist_ok=True)
                    self.page.screenshot(path=debug_path)
                except:
                    pass
                return {
                    'success': False,
                    'error': f'Failed to fill form: {str(e)}',
                    'vendors_contacted': 0
                }
            
            # Step 4: Click "Send Request" button
            try:
                send_btn = self.page.locator('button:has-text("Send Request"), button:has-text("Submit")').first
                if send_btn.is_visible():
                    send_btn.click()
                    logger.info("✓ Clicked Send Request button")
                    
                    # Wait for confirmation with a specific timeout and indicator check
                    logger.info("Waiting for confirmation message (this may take a minute)...")
                    
                    # Wait for the loading dots to disappear OR the confirmation to appear
                    try:
                        # Wait for the "three dots" loader to be hidden if it exists
                        self.page.wait_for_selector('.loading-indicator, .dots-loader', state="hidden", timeout=10000)
                    except:
                        pass
                        
                    # Now wait for the actual confirmation message
                    confirmation = "Submitted (no confirmation number found)"
                    found_confirmation = False
                    
                    # Loop for up to 60 seconds looking for success indicators
                    for _ in range(12): # 12 * 5s = 60s
                        confirmation = self._get_confirmation()
                        if confirmation and "Submitted" not in confirmation:
                            found_confirmation = True
                            break
                        
                        # Also check if we are redirected to a success page
                        if "success" in self.page.url.lower() or "confirmation" in self.page.url.lower():
                            found_confirmation = True
                            break
                            
                        time.sleep(5)
                        logger.info("...still waiting for confirmation...")
                    
                    if found_confirmation:
                        logger.info(f"✅ Successfully submitted RFQ to {selected_count} vendors")
                    else:
                        logger.warning("Could not definitively confirm submission, but clicked Send.")
                    
                    return {
                        'success': True,
                        'vendors_contacted': selected_count,
                        'confirmation': confirmation,
                        'product': product_name
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Send Request button not found',
                        'vendors_contacted': 0
                    }
                    
            except Exception as e:
                logger.error(f"Error submitting form: {e}")
                return {
                    'success': False,
                    'error': f'Failed to submit: {str(e)}',
                    'vendors_contacted': 0
                }
                
        except Exception as e:
            logger.error(f"Unexpected error in multi-vendor RFQ submission: {e}")
            # Capture error state
            try:
                debug_path = Path("logs") / f"error_{int(time.time())}.png"
                debug_path.parent.mkdir(exist_ok=True)
                self.page.screenshot(path=debug_path)
            except:
                pass
            
            # Recovery: Try to close any open modals by pressing Escape
            try:
                logger.info("Attempting recovery: Pressing Escape to close any open modals")
                self.page.keyboard.press("Escape")
                time.sleep(1)
            except:
                pass
            
            return {
                'success': False,
                'error': str(e),
                'vendors_contacted': 0
            }
