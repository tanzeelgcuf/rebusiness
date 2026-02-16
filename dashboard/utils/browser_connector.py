#!/usr/bin/env python3
"""
Browser Connector Utility
Connects to an existing Chrome browser via Chrome DevTools Protocol (CDP)
to reuse logged-in sessions and avoid IP blocking.
"""

import logging
from playwright.sync_api import sync_playwright, Browser, Page
from typing import Optional

logger = logging.getLogger(__name__)

class BrowserConnector:
    """Connects to an existing Chrome instance via CDP"""
    
    def __init__(self, cdp_url: str = "http://127.0.0.1:9222"):
        """
        Initialize browser connector
        
        Args:
            cdp_url: Chrome DevTools Protocol URL (default: http://127.0.0.1:9222)
        """
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser = None
        
    def connect(self) -> tuple[Browser, Page]:
        """
        Connect to existing Chrome browser
        
        Returns:
            Tuple of (browser, page) objects
            
        Raises:
            ConnectionError: If cannot connect to browser
        """
        try:
            logger.info(f"Connecting to Chrome at {self.cdp_url}")
            
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
            
            logger.info("Connected to browser successfully")
            
            # Try to get existing page or create new one
            contexts = self.browser.contexts
            
            if contexts and len(contexts) > 0:
                context = contexts[0]
                pages = context.pages
                
                if pages and len(pages) > 0:
                    page = pages[0]
                    logger.info(f"Using existing page: {page.url}")
                else:
                    page = context.new_page()
                    logger.info("Created new page in existing context")
            else:
                # No contexts, create a new one
                logger.info("No existing contexts, creating new context")
                context = self.browser.new_context(
                    viewport={'width': 1440, 'height': 900},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                page = context.new_page()
            
            return self.browser, page
            
        except Exception as e:
            logger.error(f"Failed to connect to browser: {e}")
            raise ConnectionError(
                f"Cannot connect to Chrome at {self.cdp_url}. "
                "Make sure Chrome is running with --remote-debugging-port=9222"
            ) from e
    
    def validate_thomasnet_login(self, page: Page) -> bool:
        """
        Check if ThomasNet is logged in on the given page
        
        Args:
            page: Playwright page object
            
        Returns:
            True if logged in, False otherwise
        """
        try:
            # Navigate to ThomasNet if not already there
            if "thomasnet.com" not in page.url:
                logger.info("Navigating to ThomasNet...")
                page.goto("https://www.thomasnet.com", timeout=30000)
                page.wait_for_load_state("networkidle")
            
            # Check for login indicators
            # Common indicators: user menu, account link, logout button
            logged_in_selectors = [
                "a[href*='account']",
                "a[href*='logout']",
                "button:has-text('Sign Out')",
                ".user-menu",
                "#user-account"
            ]
            
            for selector in logged_in_selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible(timeout=2000):
                        logger.info(f"✓ Detected login indicator: {selector}")
                        return True
                except:
                    continue
            
            # Check for login/signup buttons (indicates NOT logged in)
            login_selectors = [
                "a:has-text('Sign In')",
                "a:has-text('Log In')",
                "button:has-text('Sign In')"
            ]
            
            for selector in login_selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible(timeout=2000):
                        logger.warning(f"⚠️  Detected login button: {selector} - Not logged in")
                        return False
                except:
                    continue
            
            # If we can't definitively determine, assume logged in
            logger.info("Cannot determine login status definitively, assuming logged in")
            return True
            
        except Exception as e:
            logger.error(f"Error validating ThomasNet login: {e}")
            return False
    
    def close(self):
        """Close the browser connection"""
        if self.browser:
            try:
                # Note: Don't close the browser itself, just disconnect
                # The browser is owned by the user
                logger.info("Disconnecting from browser (browser will stay open)")
                if self.playwright:
                    self.playwright.stop()
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")


def connect_to_browser(cdp_url: str = "http://127.0.0.1:9222", 
                       validate_login: bool = True) -> tuple[Browser, Page, BrowserConnector]:
    """
    Convenience function to connect to browser and optionally validate ThomasNet login
    
    Args:
        cdp_url: Chrome DevTools Protocol URL
        validate_login: Whether to validate ThomasNet login
        
    Returns:
        Tuple of (browser, page, connector)
        
    Raises:
        ConnectionError: If cannot connect or not logged in to ThomasNet
    """
    connector = BrowserConnector(cdp_url)
    browser, page = connector.connect()
    
    if validate_login:
        if not connector.validate_thomasnet_login(page):
            connector.close()
            raise ConnectionError(
                "Not logged in to ThomasNet. Please log in first in the Chrome window."
            )
        logger.info("✓ ThomasNet login validated")
    
    return browser, page, connector


if __name__ == "__main__":
    """Test the browser connector"""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*70)
    print("Browser Connector Test")
    print("="*70)
    print()
    print("Prerequisites:")
    print("1. Chrome must be running with: --remote-debugging-port=9222")
    print("2. You should be logged in to ThomasNet")
    print()
    print("="*70)
    print()
    
    try:
        # Test connection
        browser, page, connector = connect_to_browser(validate_login=True)
        
        print("\n✅ SUCCESS!")
        print(f"   - Connected to browser")
        print(f"   - Current URL: {page.url}")
        print(f"   - ThomasNet login validated")
        print()
        
        connector.close()
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Start Chrome with remote debugging:")
        print('     /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\')
        print('       --remote-debugging-port=9222 \\')
        print('       --user-data-dir="/tmp/chrome-debug"')
        print()
        print("  2. Log in to ThomasNet in that Chrome window")
        print("  3. Run this test again")
        print()
        sys.exit(1)
