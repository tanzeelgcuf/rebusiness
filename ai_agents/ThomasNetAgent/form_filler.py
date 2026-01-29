import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

import yaml

logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent / "config.yaml"
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r") as f:
        CONFIG = yaml.safe_load(f)

class RFQFormFiller:
    """
    Handles filling and submitting RFQ forms on ThomasNet vendor pages.
    """
    
    def __init__(self, page: Page, config: Dict = None):
        self.page = page
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
            self.page.wait_for_load_state("networkidle")
            
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
                if self.page.locator(btn).first.isVisible():
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
            self.page.wait_for_load_state("networkidle")
            
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
