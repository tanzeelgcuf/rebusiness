#!/usr/bin/env python3
"""
Browser Connector Utility
Connects to an existing Chrome browser via Chrome DevTools Protocol (CDP)
to reuse logged-in sessions and avoid IP blocking.

For cloud/server deployment:
  - Run save_thomasnet_session.py on your Mac to generate auth_state.json
  - Upload auth_state.json to dashboard/ on the cloud server
  - The connector will automatically use it for headless submissions
"""

import os
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, Page
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Default auth_state.json path — always relative to the dashboard/ folder
_DASHBOARD_DIR = Path(__file__).parent.parent  # dashboard/utils/../ = dashboard/
DEFAULT_AUTH_STATE = str(_DASHBOARD_DIR / "auth_state.json")

# Load ThomasNet config for base URL fallback
_CONFIG_PATH = Path(__file__).parent.parent.parent / "ai_agents" / "ThomasNetAgent" / "config.yaml"
if _CONFIG_PATH.exists():
    with open(_CONFIG_PATH) as _f:
        CONFIG = yaml.safe_load(_f)
else:
    CONFIG = {"thomasnet": {"base_url": "https://www.thomasnet.com"}}

class BrowserConnector:
    """Connects to an existing Chrome instance via CDP"""
    
    def __init__(self, cdp_url: str = "http://127.0.0.1:9222", session_path: str = None):
        """
        Initialize browser connector
        
        Args:
            cdp_url: Chrome DevTools Protocol URL (default: http://127.0.0.1:9222)
            session_path: Path to auth_state.json file for server deployment.
                          Defaults to dashboard/auth_state.json (auto-resolved).
        """
        self.cdp_url = cdp_url
        self.session_path = session_path or DEFAULT_AUTH_STATE
        self.playwright = None
        self.browser = None
        self.context = None
        
    def connect(self, headless: bool = True) -> tuple[Browser, Page]:
        """
        Connect to browser. Attempts CDP first (local), then falls back to session file (server).
        
        Returns:
            Tuple of (browser, page) objects
        """
        import os
        from pathlib import Path
        from dotenv import load_dotenv
        
        load_dotenv()
        
        self.playwright = sync_playwright().start()
        
        # 1. Try CDP Connection (Local Debugging)
        try:
            logger.info(f"Attempting CDP connection to {self.cdp_url}...")
            self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url, timeout=5000)
            logger.info("✓ Connected via CDP successfully")
            
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
                page = self.context.pages[0] if self.context.pages else self.context.new_page()
            else:
                self.context = self.browser.new_context()
                page = self.context.new_page()
            return self.browser, page
        except Exception as e:
             logger.info(f"CDP connection failed (expected on server): {e}")

        # 2. Try Session File (Server/Cloud Deployment)
        try:
            auth_file = Path(self.session_path)
            if auth_file.exists():
                logger.info(f"🤖 Headless mode: Using saved session from {auth_file}")
                
                # Use Mac User-Agent to match the local capture environment
                user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
                
                # Proxy Configuration
                proxy_config = None
                proxy_server = os.getenv("THOMASNET_PROXY_SERVER")
                
                # 1. Check Local Gateway (Reverse Tunnel to Mac) - Priority 2
                if not proxy_server:
                    try:
                        import socket
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(0.5)
                        result = sock.connect_ex(('127.0.0.1', 9999))
                        if result == 0:
                            proxy_server = "socks5://127.0.0.1:9999"
                            logger.info("✅ Found Local Gateway Tunnel (Port 9999). Using it.")
                        sock.close()
                    except:
                        pass

                # 2. Fallback to Custom Proxy Manager - Priority 3
                if not proxy_server:
                    try:
                        from dashboard.utils.proxy_manager import proxy_manager
                        logger.info("🔄 No static proxy or gateway found. Requesting custom proxy from manager...")
                        fetched = proxy_manager.get_working_proxy()
                        if fetched:
                            proxy_server = fetched
                            logger.info(f"✅ Using Scraped Proxy: {proxy_server}")
                    except Exception as e:
                        logger.error(f"❌ Failed to get custom proxy: {e}")
                
                if proxy_server:
                    logger.info(f"🌐 Using Proxy: {proxy_server}")
                    proxy_config = {"server": proxy_server}
                    
                    # Only add auth if present (scraped proxies usually have none)
                    username = os.getenv("THOMASNET_PROXY_USERNAME")
                    password = os.getenv("THOMASNET_PROXY_PASSWORD")
                    if username and password:
                         proxy_config["username"] = username
                         proxy_config["password"] = password
                
                self.browser = self.playwright.chromium.launch(
                    headless=headless,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled'],
                    proxy=proxy_config
                )
                self.context = self.browser.new_context(
                    storage_state=str(auth_file),
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=user_agent
                )
                page = self.context.new_page()
                
                # Check if we need to solve a Captcha on start
                try:
                    page.goto(CONFIG.get("thomasnet", {}).get("base_url", "https://www.thomasnet.com"), wait_until="domcontentloaded", timeout=15000)
                    if page.frame_locator('iframe[title*="DataDome"]').first.is_visible():
                        logger.warning("⚠️ DataDome Captcha detected on launch!")
                except:
                    pass
                    
                return self.browser, page
            else:
                logger.error(f"No auth_state.json found at {auth_file} and CDP failed.")
                logger.error(f"Run: python3 save_thomasnet_session.py  (on your Mac) to generate it.")
                print(f"ERROR: auth_state.json not found at {auth_file}")
        except Exception as e:
            logger.error(f"Failed to launch browser with session: {e}")

        raise ConnectionError(
            "Could not establish browser connection. Ensure either:\n"
            "1. Chrome is running locally with --remote-debugging-port=9222\n"
            "2. Or 'auth_state.json' exists for server-side headless mode."
        )
    
    def validate_thomasnet_login(self, page: Page) -> bool:
        """
        Check if ThomasNet is logged in on the given page

        Args:
            page: Playwright page object

        Returns:
            True if logged in, False otherwise
        """
        import time  # Ensure time is available in method scope
        try:
            # Navigate to ThomasNet if not already there
            if "thomasnet.com" not in page.url:
                logger.info("Navigating to ThomasNet...")
                page.goto("https://www.thomasnet.com", wait_until="domcontentloaded", timeout=30000)
                time.sleep(2) # Give a moment for scripts to run
            
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
                       validate_login: bool = True,
                       headless: bool = True) -> tuple[Browser, Page, BrowserConnector]:
    """
    Convenience function to connect to browser and optionally validate ThomasNet login
    
    Args:
        cdp_url: Chrome DevTools Protocol URL
        validate_login: Whether to validate ThomasNet login
        headless: Whether to run in headless mode (ignored for CDP)
        
    Returns:
        Tuple of (browser, page, connector)
        
    Raises:
        ConnectionError: If cannot connect or not logged in to ThomasNet
    """
    connector = BrowserConnector(cdp_url)
    browser, page = connector.connect(headless=headless)
    
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
