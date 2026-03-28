import os
import logging
import time
from pathlib import Path
from dotenv import load_dotenv
import sys

# Add the agent directory to sys.path to allow imports
sys.path.append(str(Path(__file__).parent / "ai_agents" / "ThomasNetAgent"))

from auth import ThomasNetAuth

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("ProxyTest")

def test_connection():
    load_dotenv()
    
    proxy_url = os.getenv("THOMASNET_PROXY")
    if not proxy_url:
        logger.error("THOMASNET_PROXY not found in .env")
        return

    logger.info(f"Testing proxy connection with: {proxy_url.split('@')[-1]}") # Log only hostname for security

    auth = ThomasNetAuth(headless=True)
    try:
        page = auth.start_browser()
        
        # Test 1: Verify IP change
        logger.info("Accessing icanhazip.com for IP verification...")
        page.goto("https://ipv4.icanhazip.com", wait_until="domcontentloaded")
        ip = page.text_content("body").strip()
        logger.info(f"✅ Successfully routed through proxy. IP Address: {ip}")

        # Test 2: Verify ThomasNet access (DataDome bypass)
        logger.info("Accessing ThomasNet.com to check for DataDome blocks...")
        try:
            page.goto("https://www.thomasnet.com", wait_until="load", timeout=90000)
            
            # Check and bypass captcha
            if auth.bypass_captcha():
                logger.info("Bypass successful, proceeding with verification...")
            
            logger.info("Page reached. Waiting 5s for any dynamic content...")
            time.sleep(5)
            
            # Save HTML for debugging
            with open("logs/debug_thomasnet.html", "w") as f:
                f.write(page.content())
            
            # Check for search box as indicator of bypass
            search_box = page.locator('input[name="what"]').first
            if search_box.is_visible(timeout=10000):
                logger.info("✅ SUCCESS: ThomasNet search box is visible. DataDome bypassed!")
            else:
                logger.warning("⚠️ WARNING: Search box still not visible. Check logs/screenshot.")
                page.screenshot(path="logs/debug_thomasnet_final.png", full_page=True)
        except Exception as e:
            logger.error(f"Navigation to ThomasNet failed: {e}")
            page.screenshot(path="logs/debug_thomasnet_failed.png")
            
    except Exception as e:
        logger.error(f"❌ Proxy Test Failed: {e}")
        if auth.page:
            auth.page.screenshot(path="logs/proxy_test_error.png")
    finally:
        auth.close()

if __name__ == "__main__":
    test_connection()
