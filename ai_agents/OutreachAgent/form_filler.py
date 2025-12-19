import sys
import os
import logging
import time
from playwright.async_api import async_playwright
import asyncio

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import GEMINI_API_KEY
import google.generativeai as genai
import json

class FormFiller:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-flash-latest')
        else:
            self.model = None
            self.logger.warning("GEMINI_API_KEY not found. LLM features disabled.")

    async def find_contact_page(self, page, base_url):
        """
        Navigate to the website and try to find the 'Contact Us' page.
        """
        try:
            self.logger.info(f"Navigating to {base_url}")
            # User requested strict wait for complete loading
            await page.goto(base_url, timeout=60000, wait_until='networkidle')
            await asyncio.sleep(5) # Explicit patience for scripts
            self.logger.info(f"Page loaded (networkidle + 5s). Checking for content...")
            
            # Simple heuristic: Look for links text containing "Contact"
            contact_link = page.get_by_text("Contact", exact=False).first
            
            if await contact_link.is_visible():
                self.logger.info("Found Contact link, clicking...")
                await contact_link.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep() # Wait for contact page to settle
                return True
            else:
                self.logger.warning("Could not find 'Contact' link.")
                return False
        except Exception as e:
            self.logger.error(f"Error finding contact page: {e}")
            return False

    async def extract_emails(self, page):
        """
        Scrape the page for email addresses.
        """
        try:
            content = await page.content()
            # Stricter regex
            import re
            emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", content)
            
            ignored_domains = [
                'example.com', 'w3.org', 'sentry.io', 'domain.com', 'email.com',
                'cloudflare.com', 'google.com', 'facebook.com', 'twitter.com',
                'linkedin.com', 'youtube.com', 'instagram.com', 'github.com',
                'wix.com', 'godaddy.com', 'wordpress.com'
            ]
            
            ignored_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css']
            
            valid_emails = []
            seen = set()
            for e in emails:
                if e in seen: continue
                seen.add(e)
                
                e_lower = e.lower()
                if any(ign in e_lower.split('@')[1] for ign in ignored_domains): continue
                if any(e_lower.endswith(ext) for ext in ignored_extensions): continue
                if len(e) < 6: continue 
                
                valid_emails.append(e)
            
            if valid_emails:
                self.logger.info(f"Extracted emails: {valid_emails}")
                return valid_emails
            return []
        except Exception as e:
            self.logger.error(f"Error extracting emails: {e}")
            return []

    async def fill_form_async(self, url, data):
        """
        Attempt to fill a contact form at the given URL (Async).
        Returns dict: {'success': bool, 'extracted_emails': list, 'error': str}
        """
        result = {'success': False, 'extracted_emails': [], 'error': None}
        
        async with async_playwright() as p:
            # Launch with specific args to avoid bot detection
            browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"]) 
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Step 1: Navigate to Contact Page
            on_contact_page = await self.find_contact_page(page, url)
            if not on_contact_page:
                self.logger.info(f"Staying on {url} to check for form/emails directly.")
            
            # ALWAYS Scrape emails (whether we found contact page or not)
            result['extracted_emails'] = await self.extract_emails(page)
            
            # Step 2: Find and Analyze Form
            try:
                await page.wait_for_selector('form', timeout=5000)
                forms = await page.query_selector_all('form')
                
                target_form = None
                target_mapping = None
                
                for form in forms:
                    html = await form.inner_html()
                    # Skip tiny forms
                    if len(html) < 100: 
                        continue
                    
                    mapping = self.analyze_form(html)
                    if mapping and mapping.get('email_selector') and mapping.get('message_selector'):
                        target_form = form
                        target_mapping = mapping
                        break
                
                if target_form and target_mapping:
                    self.logger.info(f"Identified form with mapping: {target_mapping}")
                    
                    # Step 3: Fill Fields
                    async def fill_safe(selector, value):
                        if selector and value:
                            try:
                                if await page.query_selector(selector):
                                    await page.fill(selector, value)
                                    self.logger.info(f"Filled {selector}")
                                    return True
                            except Exception as e:
                                self.logger.warning(f"Failed to fill {selector}: {e}")
                            return False
                    
                    # Attempt fill
                    f1 = await fill_safe(target_mapping.get('name_selector'), data.get('name'))
                    f2 = await fill_safe(target_mapping.get('email_selector'), data.get('email'))
                    f3 = await fill_safe(target_mapping.get('message_selector'), data.get('message'))
                    await fill_safe(target_mapping.get('company_selector'), data.get('company'))
                    await fill_safe(target_mapping.get('subject_selector'), data.get('subject'))
                    
                    if f1 and f2 and f3:
                         self.logger.info("Form filled successfully. Attempting SUBMIT...")
                         
                         submit_sel = target_mapping.get('submit_selector')
                         submitted = False
                         
                         # Try specific selector first
                         if submit_sel:
                             try:
                                 await page.click(submit_sel, timeout=3000)
                                 submitted = True
                             except: pass
                        
                         # Fallback to generic submit button if specific failed or missing
                         if not submitted:
                             try:
                                 # Try clicking the form's submit button
                                 smt = await target_form.query_selector('button[type="submit"], input[type="submit"]')
                                 if smt:
                                     await smt.click(timeout=3000)
                                     submitted = True
                             except: pass

                         if submitted:
                             self.logger.info("Submit action performed.")
                             await page.wait_for_load_state("networkidle", timeout=5000)
                             result['success'] = True
                         else:
                             result['error'] = "Could not click submit button"
                    else:
                        result['error'] = "Critical fields not filled"
                else:
                    self.logger.warning("No suitable form found or LLM analysis failed.")
                    result['error'] = "No suitable form identified"

            except Exception as e:
                self.logger.error(f"Error processing form: {e}")
                result['error'] = str(e)
            
            await asyncio.sleep(3) 
            await browser.close()
            
        return result

if __name__ == "__main__":
    # Test with a dummy site or one of our suppliers
    filler = FormFiller()
    test_data = {
        "name": "John Campbell",
        "email": "john@campsable.com",
        "message": "Hello, I am interested in your pricing for industrial bolts."
    }
    # filler.fill_form("https://www.example-supplier.com", test_data) 
