"""
Vendor Email Extraction and Verification Module
Extracts and validates vendor contact emails from various sources.
"""

import re
import logging
from typing import Optional, Dict, List
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
import time

logger = logging.getLogger(__name__)

class EmailExtractor:
    """Extract and verify vendor email addresses from websites."""

    def __init__(self, page: Page):
        self.page = page

    def extract_email_from_vendor_profile(self, profile_url: str) -> Optional[str]:
        """
        Visit a ThomasNet vendor profile and extract their email.

        Args:
            profile_url: URL to vendor's ThomasNet profile page

        Returns:
            Email address if found, None otherwise
        """
        if not profile_url:
            return None

        logger.info(f"Extracting email from profile: {profile_url}")

        try:
            self.page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            # Strategy 1: Look for email in contact section
            email = self._find_email_in_page_content()
            if email:
                logger.info(f"Found email in profile: {email}")
                return email

            # Strategy 2: Check for "Request Quote" or "Contact" buttons that might show email
            email = self._extract_from_contact_modal()
            if email:
                logger.info(f"Found email in contact modal: {email}")
                return email

            # Strategy 3: Look for external website link and crawl it
            website_url = self._extract_company_website()
            if website_url:
                logger.info(f"Found company website: {website_url}")
                email = self.extract_email_from_website(website_url)
                if email:
                    return email

        except Exception as e:
            logger.error(f"Error extracting email from profile: {e}")

        return None

    def extract_email_from_website(self, website_url: str) -> Optional[str]:
        """
        Visit a company website and extract their contact email.

        Args:
            website_url: URL to company's website

        Returns:
            Email address if found, None otherwise
        """
        if not website_url or 'thomasnet.com' in website_url.lower():
            return None

        logger.info(f"Crawling website for email: {website_url}")

        try:
            # Visit homepage
            self.page.goto(website_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            # Try to find email on homepage
            email = self._find_email_in_page_content()
            if email:
                logger.info(f"Found email on homepage: {email}")
                return email

            # Try to visit contact page
            contact_url = self._find_contact_page_url()
            if contact_url:
                logger.info(f"Found contact page: {contact_url}")
                self.page.goto(contact_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)

                email = self._find_email_in_page_content()
                if email:
                    logger.info(f"Found email on contact page: {email}")
                    return email

        except Exception as e:
            logger.error(f"Error crawling website: {e}")

        return None

    def _find_email_in_page_content(self) -> Optional[str]:
        """Extract email from current page content using regex."""
        try:
            content = self.page.content()

            # Email regex pattern
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, content)

            if emails:
                # Filter out common junk emails
                ignored_domains = [
                    'example.com', 'w3.org', 'sentry.io', 'domain.com',
                    'email.com', 'cloudflare.com', 'google.com', 'facebook.com',
                    'twitter.com', 'linkedin.com', 'youtube.com', 'instagram.com',
                    'wix.com', 'godaddy.com', 'wordpress.com', 'schema.org'
                ]

                ignored_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg',
                                     '.webp', '.js', '.css', '.min.js']

                valid_emails = []
                for email in emails:
                    email_lower = email.lower()

                    # Skip if domain is in ignored list
                    domain = email_lower.split('@')[1] if '@' in email_lower else ''
                    if any(ign in domain for ign in ignored_domains):
                        continue

                    # Skip if ends with file extension
                    if any(email_lower.endswith(ext) for ext in ignored_extensions):
                        continue

                    # Skip too short
                    if len(email) < 6:
                        continue

                    valid_emails.append(email)

                if valid_emails:
                    # Return the first valid email (usually the main contact)
                    return valid_emails[0]

        except Exception as e:
            logger.error(f"Error finding email in page content: {e}")

        return None

    def _extract_from_contact_modal(self) -> Optional[str]:
        """Try to open contact modal and extract email."""
        try:
            # Look for "Contact" or "Request Quote" buttons
            contact_buttons = [
                'button:has-text("Contact")',
                'a:has-text("Contact Us")',
                'button:has-text("Request Quote")',
                'button:has-text("Get Quote")',
                '[data-testid="contact-button"]'
            ]

            for selector in contact_buttons:
                try:
                    btn = self.page.locator(selector).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                        time.sleep(2)

                        # Look for email in modal
                        email = self._find_email_in_page_content()
                        if email:
                            return email

                        # Close modal for next attempt
                        try:
                            close_btn = self.page.locator('button[aria-label="Close"]').first
                            if close_btn.count() > 0:
                                close_btn.click()
                                time.sleep(1)
                        except:
                            pass
                except:
                    continue

        except Exception as e:
            logger.debug(f"Error extracting from contact modal: {e}")

        return None

    def _extract_company_website(self) -> Optional[str]:
        """Extract company website URL from ThomasNet profile."""
        try:
            # Look for "Visit Website" or similar links
            website_selectors = [
                'a[class*="visitWebsite"]',
                'a:has-text("Visit Website")',
                'a:has-text("Company Website")',
                'a[href]:not([href*="thomasnet.com"])'
            ]

            for selector in website_selectors:
                try:
                    link = self.page.locator(selector).first
                    if link.count() > 0:
                        href = link.get_attribute('href')
                        if href and 'http' in href and 'thomasnet.com' not in href:
                            return href
                except:
                    continue

        except Exception as e:
            logger.debug(f"Error extracting company website: {e}")

        return None

    def _find_contact_page_url(self) -> Optional[str]:
        """Find the contact page URL on current website."""
        try:
            # Look for links to contact page
            contact_links = self.page.locator('a[href*="contact"]').all()

            for link in contact_links:
                href = link.get_attribute('href')
                if href:
                    # Make absolute URL
                    if href.startswith('/'):
                        current_url = self.page.url
                        from urllib.parse import urlparse
                        parsed = urlparse(current_url)
                        href = f"{parsed.scheme}://{parsed.netloc}{href}"
                    elif not href.startswith('http'):
                        continue

                    return href

        except Exception as e:
            logger.debug(f"Error finding contact page: {e}")

        return None

    def verify_email(self, email: str) -> bool:
        """
        Basic email verification (format check only).
        Real SMTP verification would require additional tools.

        Args:
            email: Email address to verify

        Returns:
            True if email format is valid
        """
        if not email:
            return False

        # Basic format check
        email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
        return bool(re.match(email_pattern, email))

    def batch_extract_emails(self, vendors: List[Dict]) -> List[Dict]:
        """
        Extract emails for a list of vendors.

        Args:
            vendors: List of vendor dictionaries with 'profile_url' and/or 'website'

        Returns:
            Updated vendor list with 'email' field added
        """
        logger.info(f"Batch extracting emails for {len(vendors)} vendors")

        for i, vendor in enumerate(vendors):
            logger.info(f"Processing vendor {i+1}/{len(vendors)}: {vendor.get('name', 'Unknown')}")

            email = None

            # Try profile URL first
            profile_url = vendor.get('profile_url')
            if profile_url:
                email = self.extract_email_from_vendor_profile(profile_url)

            # If no email found, try company website
            if not email:
                website = vendor.get('website')
                if website:
                    email = self.extract_email_from_website(website)

            vendor['email'] = email
            vendor['email_verified'] = self.verify_email(email) if email else False

            logger.info(f"  Result: {'✓ ' + email if email else '✗ No email found'}")

            # Rate limiting
            time.sleep(2)

        # Count successful extractions
        found = sum(1 for v in vendors if v.get('email'))
        logger.info(f"Email extraction complete: {found}/{len(vendors)} emails found")

        return vendors


if __name__ == "__main__":
    # Test block
    from ai_agents.ThomasNetAgent.auth import ThomasNetAuth

    with ThomasNetAuth(headless=False) as auth:
        extractor = EmailExtractor(auth.page)

        # Test with a sample vendor
        test_vendors = [
            {
                "name": "Test Vendor",
                "profile_url": "https://www.thomasnet.com/profile/12345",
                "website": "https://example-vendor.com"
            }
        ]

        results = extractor.batch_extract_emails(test_vendors)

        import json
        print(json.dumps(results, indent=2))
