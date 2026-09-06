import logging
import re
import time
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urlparse, urljoin
from playwright.sync_api import Page
from dataclasses import dataclass
import sys
import os

# Add parent directory for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

logger = logging.getLogger(__name__)


@dataclass
class VendorContact:
    """Represents extracted vendor contact information."""
    name: str
    website: str
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_form_url: Optional[str] = None
    email_verified: bool = False
    source: str = ""  # "website", "contact_page", "footer", "thomasnet_profile"
    confidence: float = 0.0


class VendorEmailExtractor:
    """
    Extracts and verifies vendor email addresses from vendor websites.
    Uses Playwright to crawl vendor sites and find contact information.
    """

    def __init__(self, page: Page, timeout: int = 30000):
        self.page = page
        self.timeout = timeout
        self.visited_urls: Set[str] = set()

        # Common ignored domains (not real company emails)
        self.ignored_email_domains = {
            'example.com', 'w3.org', 'sentry.io', 'domain.com', 'email.com',
            'cloudflare.com', 'google.com', 'facebook.com', 'twitter.com',
            'linkedin.com', 'youtube.com', 'instagram.com', 'github.com',
            'wix.com', 'godaddy.com', 'wordpress.com', 'shopify.com',
            'squarespace.com', 'weebly.com', 'typeform.com', 'hubspot.com',
            'mailchimp.com', 'constantcontact.com', 'sendgrid.com',
            'thomasnet.com', 'navigator.thomasnet.com', 'zoominfo.com',
            'dnb.com', 'manta.com', 'bbb.org', 'mapquest.com', 'yellowpages.com'
        }

        # Ignored email extensions (images, scripts, etc.)
        self.ignored_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css', '.ico', '.woff', '.woff2', '.ttf', '.eot'}

        # Email regex pattern
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

        # Phone regex pattern
        self.phone_pattern = re.compile(r'(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}')

    def extract_contacts(self, vendors: List[Dict[str, Any]], max_vendors: int = 20) -> List[VendorContact]:
        """
        Extract contact information for multiple vendors.

        Args:
            vendors: List of vendor dicts with 'name', 'website', 'profile_url'
            max_vendors: Maximum vendors to process

        Returns:
            List of VendorContact objects
        """
        contacts = []

        for i, vendor in enumerate(vendors[:max_vendors]):
            logger.info(f"[{i+1}/{min(len(vendors), max_vendors)}] Extracting contacts for: {vendor.get('name', 'Unknown')}")

            website = vendor.get('website', '')
            profile_url = vendor.get('profile_url', '')

            # Try website first (most reliable for real contact info)
            contact = None
            if website and self._is_valid_url(website):
                contact = self._extract_from_website(website, vendor.get('name', ''))
                contact.source = "website"

            # Fallback to ThomasNet profile if no email found
            if not contact or not contact.email:
                if profile_url and self._is_valid_url(profile_url):
                    logger.info(f"  Trying ThomasNet profile: {profile_url}")
                    profile_contact = self._extract_from_website(profile_url, vendor.get('name', ''))
                    if profile_contact.email:
                        contact = profile_contact
                        contact.source = "thomasnet_profile"

            if contact:
                contacts.append(contact)
                if contact.email:
                    logger.info(f"  ✓ Found email: {contact.email} (confidence: {contact.confidence:.2f})")
                else:
                    logger.info(f"  ✗ No email found")
            else:
                logger.warning(f"  ✗ Failed to extract any contact info")

            # Reset visited URLs for next vendor
            self.visited_urls.clear()

            # Small delay between vendors
            time.sleep(1)

        return contacts

    def _extract_from_website(self, url: str, vendor_name: str) -> Optional[VendorContact]:
        """Extract contact info from a vendor's website."""
        try:
            logger.info(f"  Visiting: {url}")
            self.page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
            time.sleep(2)  # Let page settle

            # Scroll to bottom to trigger lazy loading
            try:
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
            except:
                pass

            content = self.page.content()
            contact = VendorContact(name=vendor_name, website=url)

            # Extract emails from current page
            emails = self._extract_emails(content)
            if emails:
                contact.email = self._select_best_email(emails)
                contact.confidence = 0.8
                return contact

            # Try contact page
            contact_page_url = self._find_contact_page(content, url)
            if contact_page_url and contact_page_url not in self.visited_urls:
                logger.info(f"  Visiting contact page: {contact_page_url}")
                try:
                    self.page.goto(contact_page_url, timeout=self.timeout, wait_until="domcontentloaded")
                    time.sleep(2)
                    contact_content = self.page.content()
                    emails = self._extract_emails(contact_content)
                    if emails:
                        contact.email = self._select_best_email(emails)
                        contact.contact_form_url = contact_page_url
                        contact.confidence = 0.9
                        return contact

                    # Also look for contact form
                    form_url = self._find_contact_form(contact_content, contact_page_url)
                    if form_url:
                        contact.contact_form_url = form_url
                        contact.confidence = max(contact.confidence, 0.6)
                        return contact

                except Exception as e:
                    logger.warning(f"  Contact page visit failed: {e}")

            # Try footer for email
            footer_email = self._extract_from_footer(content)
            if footer_email:
                contact.email = footer_email
                contact.confidence = 0.7
                contact.source = "footer"
                return contact

            return contact

        except Exception as e:
            logger.warning(f"  Failed to visit {url}: {e}")
            return VendorContact(name=vendor_name, website=url)

    def _extract_emails(self, html: str) -> List[str]:
        """Extract valid emails from HTML content."""
        emails = self.email_pattern.findall(html)
        valid_emails = []

        for email in emails:
            email_lower = email.lower()

            # Skip ignored domains
            domain = email_lower.split('@')[1] if '@' in email_lower else ''
            if any(ignored in domain for ignored in self.ignored_email_domains):
                continue

            # Skip ignored extensions
            if any(email_lower.endswith(ext) for ext in self.ignored_extensions):
                continue

            # Skip very short or suspicious emails
            if len(email) < 6:
                continue
            if email_lower.startswith(('noreply', 'no-reply', 'donotreply', 'info@', 'support@', 'sales@', 'admin@', 'webmaster@', 'postmaster@')):
                # These are generic - prefer specific contacts
                pass

            valid_emails.append(email)

        return valid_emails

    def _select_best_email(self, emails: List[str]) -> str:
        """Select the most likely real contact email from a list."""
        # Prefer non-generic emails
        generic_prefixes = {'info', 'support', 'sales', 'admin', 'contact', 'hello', 'inquiries', 'noreply', 'donotreply', 'postmaster', 'webmaster'}

        # Score emails: non-generic > shorter domain > first found
        scored = []
        for email in emails:
            local_part = email.split('@')[0].lower()
            is_generic = local_part in generic_prefixes
            score = (0 if is_generic else 10) + (100 / len(email))  # Prefer shorter, non-generic
            scored.append((score, email))

        scored.sort(key=lambda x: -x[0])
        return scored[0][1] if scored else emails[0]

    def _find_contact_page(self, html: str, base_url: str) -> Optional[str]:
        """Find contact page URL from HTML."""
        # Common contact page paths
        contact_paths = [
            '/contact', '/contact-us', '/contactus', '/get-in-touch',
            '/about/contact', '/about-us/contact', '/company/contact',
            '/reach-us', '/connect', '/request-quote', '/quote'
        ]

        # First, look for explicit contact links in the page
        contact_link_patterns = [
            r'href=["\']([^"\']*(?:contact|Contact)[^"\']*)["\']',
            r'href=["\']([^"\']*(?:get-in-touch|reach-us|connect)[^"\']*)["\']',
        ]

        for pattern in contact_link_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                full_url = urljoin(base_url, match)
                if self._is_valid_url(full_url):
                    return full_url

        # Fallback: try common paths
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in contact_paths:
            candidate = base + path
            if self._is_valid_url(candidate):
                return candidate

        return None

    def _find_contact_form(self, html: str, current_url: str) -> Optional[str]:
        """Check if page has a contact form."""
        form_indicators = [
            '<form', 'type="email"', 'name="email"', 'id="email"',
            'placeholder="email"', 'placeholder="Email"', 'contact-form',
            'ContactForm', 'contact_form', 'wpcf7', 'gform'
        ]

        if any(indicator in html for indicator in form_indicators):
            return current_url
        return None

    def _extract_from_footer(self, html: str) -> Optional[str]:
        """Extract email from footer section."""
        # Look for footer content
        footer_markers = ['<footer', 'class="footer', 'id="footer', 'class="site-footer']
        footer_start = -1

        for marker in footer_markers:
            idx = html.lower().find(marker.lower())
            if idx != -1:
                footer_start = idx
                break

        if footer_start == -1:
            # Try bottom 20% of page
            footer_start = int(len(html) * 0.8)

        footer_html = html[footer_start:]
        emails = self._extract_emails(footer_html)
        return emails[0] if emails else None

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and accessible."""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except:
            return False


def extract_vendor_emails(vendors: List[Dict[str, Any]], page: Page, max_vendors: int = 20) -> List[VendorContact]:
    """
    Convenience function to extract vendor emails.

    Args:
        vendors: List of vendor dicts
        page: Playwright page object
        max_vendors: Maximum vendors to process

    Returns:
        List of VendorContact objects with email info
    """
    extractor = VendorEmailExtractor(page)
    return extractor.extract_contacts(vendors, max_vendors)


if __name__ == "__main__":
    # Test with a simple example
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

    from ai_agents.ThomasNetAgent.auth import ThomasNetAuth
    from ai_agents.ThomasNetAgent.searcher import ThomasNetSearch

    with ThomasNetAuth(headless=True) as auth:
        search = ThomasNetSearch(auth)
        vendors = search.search_vendors("industrial fasteners", max_results=5)

        contacts = extract_vendor_emails(vendors, auth.page, max_vendors=3)

        for contact in contacts:
            print(f"\nVendor: {contact.name}")
            print(f"  Website: {contact.website}")
            print(f"  Email: {contact.email}")
            print(f"  Phone: {contact.phone}")
            print(f"  Contact Form: {contact.contact_form_url}")
            print(f"  Confidence: {contact.confidence:.2f}")
            print(f"  Source: {contact.source}")