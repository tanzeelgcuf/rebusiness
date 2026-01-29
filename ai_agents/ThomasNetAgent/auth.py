import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator

from playwright_stealth import Stealth

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Playwright
# ... (rest of imports)

# ... (inside ThomasNetAuth class)


import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent / "config.yaml"
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r") as f:
        CONFIG = yaml.safe_load(f)
else:
    # Fallback default config if file missing
    CONFIG = {
        "thomasnet": {
            "base_url": "https://www.thomasnet.com",
            "login_url": "https://www.thomasnet.com/account/login",
            "headless": True,
            "browser_timeout": 30000,
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    }

class ThomasNetAuth:
    """
    Handles authentication and browser session management for ThomasNet.
    """
    
    def __init__(self, headless: Optional[bool] = None):
        """
        Initialize auth handler.
        
        Args:
            headless: Override config headless setting if provided
        """
        self.email = os.getenv("THOMASNET_EMAIL")
        self.password = os.getenv("THOMASNET_PASSWORD")
        
        # Use config value if headless not specified
        if headless is None:
            self.headless = CONFIG["thomasnet"].get("headless", True)
        else:
            self.headless = headless
            
        self.proxy_url = os.getenv("THOMASNET_PROXY")
            
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start_browser(self) -> Page:
        """Start browser and return a page object."""
        self.playwright = sync_playwright().start()
        
        browser_type_name = CONFIG["thomasnet"].get("browser_type", "chromium").lower()
        
        if browser_type_name == "firefox":
            browser_type = self.playwright.firefox
        elif browser_type_name == "webkit":
            browser_type = self.playwright.webkit
        else:
            browser_type = self.playwright.chromium

        # Recent User Agent for Mac (Chrome 121)
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certificate-errors",
            "--disable-extensions",
            "--disable-dev-shm-usage",
        ]

        # Use persistent context to save session/cookies
        user_data_dir = Path(__file__).parent / "chrome_profile"
        user_data_dir.mkdir(exist_ok=True)
        
        # Prepare proxy config if available
        proxy_config = None
        if self.proxy_url:
            proxy_config = {"server": self.proxy_url}
            # If using authenticated proxy, username/pass are usually in the URL
            # e.g. http://user:pass@host:port
            logger.info(f"Using proxy: {self.proxy_url}")

        self.context = browser_type.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=self.headless,
            args=args,
            proxy=proxy_config,
            user_agent=user_agent,
            viewport={'width': 1440, 'height': 900},
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"]
        )
        
        self.browser = None # persistent context manages browser process
        
        # Add init script to remove webdriver property
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        # Set default timeout
        self.context.set_default_timeout(CONFIG["thomasnet"]["browser_timeout"])
        
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        
        # Apply stealth only for Chromium
        if CONFIG["thomasnet"].get("browser_type", "chromium") == "chromium":
            Stealth().apply_stealth_sync(self.page) 
            
        return self.page

    def login(self) -> bool:
        """
        Log in to ThomasNet.
        
        Returns:
            bool: True if login successful, False otherwise
        """
        if not self.page:
            self.start_browser()

        logger.info("Navigate to login page...")
        try:
            self.page.goto(CONFIG["thomasnet"]["login_url"])
            
            # Check if already logged in (redirected to home or dashboard)
            if "login" not in self.page.url:
                logger.info("Already logged in.")
                return True

            if not self.email or not self.password:
                logger.error("Missing THOMASNET_EMAIL or THOMASNET_PASSWORD env variables")
                return False

            # Selector strategy for 2-step login (Auth0 style)
            logger.info(f"Attempting login as {self.email}...")
            
            # Step 1: Handling DataDome, Homepage Redirects, and Login Form
            email_input_found = False
            start_time = time.time()
            max_wait = 300 # 5 minutes
            
            logger.info("Waiting for login form (solving Captcha or navigating)...")
            
            while time.time() - start_time < max_wait:
                # 1. Check if we are already seeing the email input
                if self.page.locator('input[type="email"]').is_visible():
                    logger.info("Login form detected.")
                    email_input_found = True
                    break
                
                # 2. Check for DataDome Captcha
                try:
                    if self.page.frame_locator('iframe[title*="DataDome"]').first.is_visible(timeout=100):
                        logger.warning("⚠️ DataDome Captcha detected! Please solve it manually.")
                        time.sleep(2)
                        continue
                except:
                    pass

                # 3. Check if we are on Homepage and need to click Login
                # Selector based on observed HTML: class="login-button_loginButton__u1Avl"
                try:
                    login_btn = self.page.locator('button:has-text("Login")').first
                    if login_btn.is_visible(timeout=100) and "thomasnet.com" in self.page.url:
                        logger.info("Detected Homepage/Nav bar. Clicking 'Login' button...")
                        login_btn.click()
                        time.sleep(2) # Wait for navigation
                        continue
                except:
                    pass

                time.sleep(1)
            
            if not email_input_found:
                raise Exception("Timed out waiting for login form or email input.")

            # Step 1a: Fill Email
            logger.info("Filling email...")
            self.page.fill('input[type="email"]', self.email)
            
            # Strategy 1: Press Enter
            logger.info("Pressing Enter to submit email...")
            self.page.press('input[type="email"]', 'Enter')
            
            # Wait briefly to see if it worked
            try:
                self.page.wait_for_selector('input[type="password"]', state='visible', timeout=5000)
                logger.info("Password field appeared after pressing Enter.")
            except:
                logger.info("Enter didn't work immediately. Trying button click...")
                
                # Strategy 2: Click Button
                # Try generic "Continue" or "Next" text matching first, as it's more robust than specific classes
                if self.page.locator('button:has-text("Continue")').first.is_visible():
                     self.page.locator('button:has-text("Continue")').first.click()
                elif self.page.locator('button:has-text("Next")').first.is_visible():
                     self.page.locator('button:has-text("Next")').first.click()
                elif self.page.locator('form._form-login-id button[type="submit"]').first.is_visible():
                    self.page.locator('form._form-login-id button[type="submit"]').first.click()
                elif self.page.locator('button[type="submit"]').first.is_visible():
                    self.page.locator('button[type="submit"]').first.click()
                else:
                    logger.error("Could not find any login submit button.")
            
            logger.info("Submitted email, waiting for password field...")

            # Step 2: Password
            try:
                # Wait for password input to appear (it might animate in)
                self.page.wait_for_selector('input[type="password"]', state='visible', timeout=10000)
                self.page.fill('input[type="password"]', self.password)
                
                # Click "Login"
                # Often in Auth0 it's a button with type="submit" inside form._form-login-password
                if self.page.locator('form._form-login-password button[type="submit"]').first.is_visible():
                     self.page.locator('form._form-login-password button[type="submit"]').first.click()
                else:
                     # Generic fallback
                     self.page.locator('button[type="submit"]').first.click()
                     
                logger.info("Submitted password...")
            except Exception as e:
                 logger.error(f"Step 2 (Password) failed: {e}")
                 raise e
            
            # Wait for navigation
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            except:
                pass # Proceed even if timeout, as we verify URL anyway
            
            # Verification check
            # Look for indicators of success (e.g., "My Account", "Log Out", specific dashboard element)
            # This is a generic check, might need refinement
            if "login" not in self.page.url or self.page.locator('text=Log Out').is_visible():
                logger.info("Login successful!")
                return True
            
        except Exception as e:
            logger.error(f"Login process failed: {str(e)}")
            # Take screenshot for debugging
            if self.page:
                debug_dir = Path("logs")
                debug_dir.mkdir(exist_ok=True)
                self.page.screenshot(path=debug_dir / "login_error.png")
                with open(debug_dir / "login_error.html", "w") as f:
                    f.write(self.page.content())
            return False

    def close(self):
        """Close browser resources."""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def __enter__(self):
        self.start_browser()
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

if __name__ == "__main__":
    # Simple test
    with ThomasNetAuth(headless=False) as auth:
        print("Browser started and login attempted")
        time.sleep(5)  # Keep open for 5s to see
