import logging
import time
from typing import List, Dict, Any, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

import yaml
from pathlib import Path

# Load config
CONFIG_PATH = Path(__file__).parent / "config.yaml"
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r") as f:
        CONFIG = yaml.safe_load(f)

logger = logging.getLogger(__name__)

class ThomasNetSearch:
    """
    Handles searching for vendors on ThomasNet and parsing results.
    """
    
    def __init__(self, page: Page):
        self.page = page
        self.base_url = CONFIG["thomasnet"]["base_url"]

    def search_vendors(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Search for vendors matching the query string.
        
        Args:
            query: Product or service to search for
            max_results: Maximum number of vendors to return
            
        Returns:
            List of dictionaries containing vendor info
        """
        logger.info(f"Searching for: {query}")
        
        # Navigate to home if not there
        if self.base_url not in self.page.url:
            self.page.goto(self.base_url)
            
        # 1. Perform Search
        try:
            # Try to find the search box.
            # Selector strategy based on observed HTML
            search_input = self.page.locator('input[data-ref="srp.DiscoverBox.input"]').first
            if not search_input.is_visible():
                # Fallback selectors
                search_input = self.page.locator('input[placeholder*="Describe what you\'re looking for"]').first
                
            if not search_input.is_visible():
                search_input = self.page.locator('input[name="term"]').first
                
            if not search_input.is_visible():
                logger.error(f"Could not find search input field. Current URL: {self.page.url}")
                # Debug snapshots
                debug_dir = Path("logs")
                debug_dir.mkdir(exist_ok=True)
                self.page.screenshot(path=debug_dir / "search_input_fail.png")
                with open(debug_dir / "search_input_fail.html", "w") as f:
                    f.write(self.page.content())
                return []
             
            import random
            
            # Human-like typing
            logger.info(f"Typing query '{query}' like a human...")
            search_input.click()
            time.sleep(random.uniform(0.5, 1.5))
            
            for char in query:
                search_input.type(char, delay=random.uniform(50, 200)) # Random delay between keystrokes
                
            time.sleep(random.uniform(0.8, 1.5))
            search_input.press("Enter")
            
            # Wait for results to load
            try: 
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            except:
                pass

            # Check for DataDome Captcha on search results
            try:
                # Poll for a few seconds to see if Captcha appears
                for _ in range(5):
                    if self.page.frame_locator('iframe[title*="DataDome"]').first.is_visible():
                        logger.warning("⚠️ DataDome Captcha detected on search results! Please solve it manually.")
                        logger.warning("Waiting up to 5 minutes for manual completion...")
                        
                        # Wait for captcha to disappear or user to solve it
                        # We'll wait for a known element of the search results to appear
                        try:
                            self.page.wait_for_selector('.vendor-card, .supplier-card, .company-listing', timeout=300000) # 5 mins
                            logger.info("Captcha solved/bypassed. Search results loaded.")
                        except:
                            logger.error("Timed out waiting for search results after Captcha.")
                        break
                    time.sleep(1)
            except Exception as e:
                logger.debug(f"Captcha check ignored: {e}")
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
            
        # 2. Parse Results
        return self._parse_results(max_results)

    def _parse_results(self, max_results: int) -> List[Dict[str, Any]]:
        """Parse vendor cards from search results page."""
        vendors = []
        
        # Vendor cards usually have a specific class
        # This is a BEST GUESS based on common structures. 
        # Will likely need adjustment after first live test.
        # Looking for containers that likely hold vendor info
        
        try:
            # Wait for at least one result
            self.page.wait_for_selector('.vendor-card, .supplier-card, .company-listing', timeout=5000)
        except PlaywrightTimeoutError:
            logger.warning("No standard vendor cards found. Check selectors.")
            # Take screenshot for debugging
            debug_path = Path("logs") / "search_debug.png"
            debug_path.parent.mkdir(exist_ok=True)
            self.page.screenshot(path=debug_path)
            # Try to infer structure broadly if specific class fails
            # return [] # For now, return empty to be safe
        
        # Generic strategy to find result containers
        # We'll look for repeated elements that look like listings
        cards = self.page.locator('div[data-role="supplier-card"], div.supplier-card, div.profile-card').all()
        
        if not cards:
            logger.warning("No vendor cards found with primary selectors.")
            # Debug: Save HTML to inspect structure
            try:
                Path("logs").mkdir(exist_ok=True) # Ensure logs directory exists
                with open("logs/search_results.html", "w", encoding="utf-8") as f:
                    f.write(self.page.content())
                self.page.screenshot(path="logs/search_results.png")
                logger.info("Saved search results debug files to logs/")
            except Exception as e:
                logger.error(f"Failed to save debug info: {e}")
            return []
            
        logger.info(f"Found {len(cards)} potential vendors. Parsing top {max_results}...")
        
        for idx, card in enumerate(cards):
            if idx >= max_results:
                break
                
            try:
                # Name
                name_el = card.locator('h2, h3, .company-name').first
                name = name_el.inner_text().strip() if name_el.is_visible() else "Unknown Vendor"
                
                # Profile Link
                link_el = card.locator('a[href*="/profile/"]').first
                profile_url = ""
                if link_el.is_visible():
                    href = link_el.get_attribute("href")
                    if href:
                        profile_url = self.base_url + href if href.startswith("/") else href
                
                # Location (City, State)
                loc_el = card.locator('.location, .address, span[itemprop="addressLocality"]').first
                location = loc_el.inner_text().strip() if loc_el.is_visible() else "Unknown Location"
                
                # Rating (if available) - e.g. stars or badges
                rating = 0.0
                rating_el = card.locator('.stars, .rating').first
                if rating_el.is_visible():
                    # Heuristic parsing of rating
                    text = rating_el.get_attribute("aria-label") or rating_el.inner_text()
                    # extract float
                    import re
                    match = re.search(r'(\d+(\.\d+)?)', text)
                    if match:
                        rating = float(match.group(1))

                # Verification Status
                verified = False
                if card.locator('.verified, .registered, .certified').count() > 0:
                    verified = True
                    
                vendor_data = {
                    "rank": idx + 1,
                    "name": name,
                    "profile_url": profile_url,
                    "location": location,
                    "rating": rating,
                    "verified": verified
                }
                
                vendors.append(vendor_data)
                
            except Exception as e:
                logger.warning(f"Error parsing vendor card {idx}: {e}")
                continue
                
        return vendors

if __name__ == "__main__":
    # Test block requires authenticated session normally, 
    # but we can try search without login for some sites
    from auth import ThomasNetAuth
    
    with ThomasNetAuth(headless=False) as auth:
        # auth.start_browser() # Already started in __enter__
        search = ThomasNetSearch(auth.page)
        results = search.search_vendors("fasteners", max_results=5)
        import json
        print(json.dumps(results, indent=2))
        time.sleep(2)
