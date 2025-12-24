import sys
import os
import logging
import time
from playwright.async_api import async_playwright
import asyncio
from bs4 import BeautifulSoup

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import GEMINI_API_KEY
import google.generativeai as genai
import json
from .email_service import EmailService

# Identity Configuration
IDENTITY = {
    "FIRST_NAME": "John",
    "LAST_NAME": "Campbell",
    "FULL_NAME": "John Campbell",
    "EMAIL": "john@campsable.com",
    "PHONE": "720-980-6080",
    "COMPANY": "Camp Sable, LLC",
    "JOB_TITLE": "Procurement Manager"
}

class FormFiller:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        else:
            self.model = None
            self.logger.warning("GEMINI_API_KEY not found. LLM features disabled.")
            
        # Initialize Email Service (Credentials will be passed at runtime or fetched from env)
        # Assuming we use the credentials associated with the identity
        self.email_service = None 

    def generate_rfq_message(self, product_name, notice_id=None, quantity="Not Specified", due_date="ASAP"):
        """
        Generates the specific RFQ message requested by the user.
        """
        today = time.strftime("%B %d, %Y")
        notice_ref = f"[{notice_id}]" if notice_id else ""
        
        template = f"""Camp Sable, LLC
{IDENTITY['EMAIL']}
{today}

Subject: Request for Quote - {notice_ref} {product_name}

Dear Sales Department:

We are writing to request a formal quote for {product_name}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement company.

Project Details:
Product/Service Required: {product_name}
Quantity Needed: {quantity}
Specifications/Requirements: Standard commercial specifications for government acquisition.
Delivery Timeline: {due_date}
Delivery Location: Continental US (CONUS) - Specifics provided upon award.

Quote Requirements: Please include the following in your response:
- Itemized pricing breakdown
- Delivery schedule and shipping costs
- Warranty information

Response Deadline: We require your quote to be submitted no later than 4 days from today to ensure timely evaluation of all proposals.

If you have any questions regarding this request or need additional information, please contact me at {IDENTITY['EMAIL']}. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

Sincerely,

{IDENTITY['FULL_NAME']}
{IDENTITY['JOB_TITLE']}
{IDENTITY['COMPANY']}
"""
        return template

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
                await asyncio.sleep(5) # Wait for contact page to settle
                return True
            else:
                self.logger.warning("Could not find 'Contact' link.")
                return False
        except Exception as e:
            self.logger.error(f"Error finding contact page: {e}")
            return False

    async def _handle_captcha(self, page):
        """
        Detects and handles CAPTCHA by pausing for manual user intervention being run in headful mode.
        """
        try:
            # Common Captcha Selectors
            captcha_selectors = [
                'iframe[src*="recaptcha"]',
                'iframe[src*="hcaptcha"]', 
                '#g-recaptcha',
                '.g-recaptcha',
                'iframe[src*="turnstile"]'
            ]
            
            found = False
            for sel in captcha_selectors:
                if await page.query_selector(sel):
                    found = True
                    break
            
            # Text Heuristics
            if not found:
                 content = await page.content()
                 if "i'm not a robot" in content.lower() or "security check" in content.lower():
                     found = True
            
            if found:
                self.logger.warning("⚠️ CAPTCHA DETECTED! Pausing for 45s to allow manual solution...")
                # If running headful, user can solve it.
                await asyncio.sleep(45)
                self.logger.info("Resuming after Captcha pause...")
                return True
        except Exception as e:
            self.logger.warning(f"Error checking captcha: {e}")
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
                'wix.com', 'godaddy.com', 'wordpress.com', 'amazonses.com',
                'myshopify.com', 'shopify.com', '2x.png', '3x.png' # Common false positives
            ]
            
            ignored_patterns = [
                'noreply', 'no-reply', 'donotreply', 'support-icon', 'user-icon',
                'u-20', 'u-21', 'u-22', # hex codes often mistaken
                'test@', 'me@', 'you@', 'user@', 'admin@domain', 'name@'
            ]
            
            ignored_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css', '.bmp', '.tif']
            
            valid_emails = []
            seen = set()
            for e in emails:
                if e in seen: continue
                seen.add(e)
                
                e_lower = e.lower()
                user_part, domain_part = e_lower.split('@')

                if any(ign in domain_part for ign in ignored_domains): continue
                if any(pat in user_part for pat in ignored_patterns): continue
                if any(e_lower.endswith(ext) for ext in ignored_extensions): continue
                
                # Filter out "u-1834..." style generated IDs
                if re.match(r'^u-\d+', user_part): continue
                
                # Filter out pure numbers
                if user_part.isdigit(): continue

                if len(e) < 6: continue 
                
                valid_emails.append(e)
            
            if valid_emails:
                self.logger.info(f"Extracted emails: {valid_emails}")
                return valid_emails
            return []
        except Exception as e:
            self.logger.error(f"Error extracting emails: {e}")
            return []
    def analyze_form(self, form_html):
        """
        Heuristic analysis of form HTML to identify field selectors.
        Returns a mapping dict or None.
        """
        try:
            soup = BeautifulSoup(form_html, 'html.parser')
            mapping = {}
            
            def find_input(keywords, type_filter=None, tag='input'):
                # Helper to find input by heuristics
                elements = soup.find_all(tag)
                for el in elements:
                    attrs = (el.get('name', '') + ' ' + el.get('id', '') + ' ' + el.get('placeholder', '')).lower()
                    if type_filter and el.get('type') != type_filter:
                         if type_filter == 'email' and 'email' in attrs: pass # Allow if name has email
                         else: continue
                    
                    for kw in keywords:
                        if kw in attrs:
                            # Return CSS selector
                            if el.get('id'): return f"{tag}#{el.get('id')}"
                            if el.get('name'): return f"{tag}[name='{el.get('name')}']"
                            return None
                return None

            # Name
            mapping['name_selector'] = find_input(['name', 'full name', 'first name', 'contact'], tag='input')
            
            # Email
            mapping['email_selector'] = find_input(['email', 'e-mail'], type_filter='email')
            if not mapping['email_selector']: # Fallback
                mapping['email_selector'] = find_input(['email', 'e-mail'], tag='input')

            # Company
            mapping['company_selector'] = find_input(['company', 'business', 'organization'], tag='input')
            
            # Subject
            mapping['subject_selector'] = find_input(['subject', 'topic'], tag='input')
            
            # Message
            mapping['message_selector'] = find_input(['message', 'comment', 'detail', 'inquiry'], tag='textarea')
            if not mapping['message_selector']:
                 mapping['message_selector'] = find_input(['message', 'comment'], tag='input') # Sometimes input type=text
            
            # Submit
            submit_btn = soup.find('button', type='submit') or soup.find('input', type='submit')
            if submit_btn:
                if submit_btn.get('id'): mapping['submit_selector'] = f"#{submit_btn.get('id')}"
                elif submit_btn.get('name'): mapping['submit_selector'] = f"[name='{submit_btn.get('name')}']"
                else: mapping['submit_selector'] = 'button[type="submit"]' # Generic fallback
            else:
                 mapping['submit_selector'] = 'button[type="submit"]'

            # Valid if we have at least Email and Message? Or Name?
            if mapping.get('email_selector'):
                return mapping
            return None
            
        except Exception as e:
            self.logger.error(f"Heuristic analysis failed: {e}")
            return None
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
            
            # Check for Captcha on arrival
            await self._handle_captcha(page)
            
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


    async def process_supplier_outreach(self, supplier_url, product_details):
        """
        Orchestrates the full outreach workflow for a single supplier:
        1. Visit Website
        2. Extract Emails (always)
        3. Fill Contact Form (if found)
        4. Send Email to extracted addresses
        """
        self.logger.info(f"--- Starting Outreach for {supplier_url} ---")
        
        # 1. Generate Content
        subject = f"Request for Quote - {product_details['product_name']}"
        message_body = self.generate_rfq_message(
            product_details['product_name'], 
            notice_id=product_details.get('notice_id'),
            quantity=product_details.get('quantity', 'Not Specified'),
            due_date=product_details.get('due_date', 'ASAP')
        )
        
        form_data = {
            "name": IDENTITY['FULL_NAME'],
            "email": IDENTITY['EMAIL'],
            "phone": IDENTITY['PHONE'],
            "company": IDENTITY['COMPANY'],
            "subject": subject,
            "message": message_body
        }

        outreach_result = {
            "form_filled": False,
            "emails_found": [],
            "emails_sent": 0,
            "error": None
        }

        # 2. Browser Interaction (Visit -> Extract -> Form)
        # We reuse fill_form_async logic but need access to extracted emails even if form fails
        # So we call fill_form_async which returns {'extracted_emails': [], 'success': bool}
        try:
            form_result = await self.fill_form_async(supplier_url, form_data)
            outreach_result['form_filled'] = form_result['success']
            outreach_result['emails_found'] = form_result['extracted_emails']
            if form_result['error']:
                self.logger.warning(f"Form fill issue: {form_result['error']}")
        except Exception as e:
            self.logger.error(f"Browser interaction failed: {e}")
            outreach_result['error'] = str(e)

        # 3. Send Emails
        # We need to initialize EmailService if not already done
        if not self.email_service:
            # TRY TO FIND CREDS or use hardcoded fallback from prompt context
            # WARNING: Using hardcoded app password found in previous artifacts for 'john@campsable.com' context
            self.email_service = EmailService(
                smtp_server="smtp.gmail.com",
                smtp_port=587,
                sender_email=IDENTITY['EMAIL'],
                sender_password="gwun semw qdwo ckxz" 
            )
        
        if outreach_result['emails_found']:
            self.logger.info(f"Sending emails to {len(outreach_result['emails_found'])} recipients...")
            for recipient in outreach_result['emails_found']:
                try:
                    sent = self.email_service.send_email(
                        to_email=recipient,
                        subject=subject,
                        body=message_body
                    )
                    if sent:
                        outreach_result['emails_sent'] += 1
                        time.sleep(1) # Rate limit
                except Exception as e:
                    self.logger.error(f"Email send failed to {recipient}: {e}")
        else:
            self.logger.info("No emails found to send.")

        return outreach_result

if __name__ == "__main__":
    # Test
    filler = FormFiller()
    # async run
    # asyncio.run(filler.process_supplier_outreach("https://example.com", {'product_name': 'Test Widget'}))

