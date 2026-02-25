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
        
        # Instead of using the search box, navigate directly to the search results URL
        # This ensures we get the full page with JSON-LD data
        # ThomasNet search URLs follow the pattern: /suppliers/usa/{query-slug}
        # Convert query to URL slug (lowercase, replace spaces with hyphens)
        import re
        query_slug = re.sub(r'[^\w\s-]', '', query.lower())
        query_slug = re.sub(r'[-\s]+', '-', query_slug).strip('-')
        
        
        # ALWAYS use search box workflow as recommended by user
        logger.info(f"Searching for '{query}' using search box workflow on ThomasNet")
        
        # Step 1: Navigate to ThomasNet Homepage (User Request)
        logger.info("Step 1: Navigating to thomasnet.com...")
        try:
            # Navigate to homepage
            self.page.goto("https://www.thomasnet.com/", wait_until="domcontentloaded", timeout=60000)
            logger.info(f"✓ Loaded homepage: {self.page.url}")
            time.sleep(3)  # Human-like delay
            
        except Exception as e:
            logger.error(f"Failed to load ThomasNet homepage: {e}")
            return []
        
        logger.info("Finding search box...")
        try:
            # Try specific user-provided selector first (from HTML snippet)
            # <input ... data-ref="srp.DiscoverBox.input" ...>
            search_selectors = [
                 'input[data-ref="srp.DiscoverBox.input"]',
                 'input[placeholder*="Discover suppliers"]',
                 '#search-input',
                 'input[name="term"]',
            ]
            
            search_input = None
            for selector in search_selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.is_visible():
                        search_input = element
                        logger.info(f"✓ Found search box with selector: {selector}")
                        break
                except:
                     pass

            if not search_input:
                logger.warning("Could not find search box with standard selectors. Checking shadow DOM/frames...")
                # Try finding ANY input that looks like search
                inputs = self.page.locator('input[type="text"]').all()
                for inp in inputs:
                    ph = inp.get_attribute("placeholder")
                    if ph and ("suppliers" in ph.lower() or "search" in ph.lower()):
                         search_input = inp
                         logger.info(f"✓ Found potential search box by placeholder: {ph}")
                         break

            if not search_input:
                # Debug dump
                logger.error("Saved page HTML to logs/search_page_debug.html for debugging")
                with open("logs/search_page_debug.html", "w") as f:
                    f.write(self.page.content())
                raise Exception("Search box not found (debug HTML saved)")

            # Type query
            logger.info(f"Typing query: {query}")
            search_input.click()
            search_input.fill("")
            time.sleep(0.5)
            # Type slowly for realism
            search_input.type(query, delay=100)
            time.sleep(1)
            search_input.press("Enter")
            
            # Final check - wait for actual result elements
            logger.info("Verifying search results are visible...")
            try:
                # Common result containers
                self.page.wait_for_selector('li[data-sentry-component*="SearchResult"], .supplier-card, li:has(h2), .SearchResultSupplier', timeout=15000)
                logger.info("✓ Search results detected on page")
            except:
                logger.warning("Could not find specific result elements, but proceeding with parse...")

            logger.info(f"✓ Search completed for: {query}")

        except Exception as e:
            logger.error(f"Failed to find or fill search box: {e}")
            return []
        
        # Step 4: Check for DataDome Captcha
        try:
            for _ in range(3):
                if self.page.frame_locator('iframe[title*="DataDome"]').first.is_visible():
                    logger.warning("⚠️  DataDome Captcha detected! Please solve it manually.")
                    logger.warning("Waiting up to 5 minutes for manual completion...")
                    try:
                        self.page.wait_for_selector('li:has(h2)', timeout=300000)
                        logger.info("✓ Captcha solved. Page loaded.")
                    except:
                        logger.error("Timed out waiting for page after Captcha.")
                    break
                time.sleep(1)
        except Exception as e:
            logger.debug(f"Captcha check ignored: {e}")
        
        # Step 5: Clear Supplier Cart (Post-Search)
        # User feedback: The cart appears on the search results page and must be cleared here.
        logger.info("Step 4: Clearing Supplier Cart on search results page...")
        self.clear_supplier_cart()
        
        # Step 6: Parse results
        logger.info("Step 5: Parsing search results...")
        return self._parse_results(max_results)

    def clear_supplier_cart(self):
        """
        Check for and clear any previously selected vendors in the 'Supplier Cart'.
        This prevents cross-contamination between RFQ submissions.
        """
        try:
            logger.info("Checking for existing Supplier Cart to clear...")
            
            # Selectors for the "Remove supplier" buttons in the cart/chips
            # The user explicitly provided: <button slot="close" aria-label="Remove supplier"></button>
            remove_btn_selectors = [
                'button[slot="close"][aria-label="Remove supplier"]',  # Primary user-confirmed selector
                'l-chip button[slot="close"]',  # Wider match
                'button[aria-label="Remove supplier"]',
                '.supplier-cart .remove-btn',
                '[data-testid="remove-supplier-btn"]'
            ]
            
            cleared_count = 0
            max_attempts = 10
            
            for _ in range(max_attempts):
                found_any = False
                for selector in remove_btn_selectors:
                    buttons = self.page.locator(selector)
                    count = buttons.count()
                    
                    if count > 0:
                        logger.info(f"Found {count} vendor(s) to remove with selector: {selector}")
                        
                        # Iterate backwards to avoid index issues as elements are removed
                        for i in range(count - 1, -1, -1):
                            try:
                                btn = buttons.nth(i)
                                if btn.is_visible():
                                    btn.click()
                                    cleared_count += 1
                                    found_any = True
                                    time.sleep(0.5)  # Brief pause for UI update
                            except Exception as e:
                                logger.warning(f"Failed to click remove button: {e}")
                
                if not found_any:
                    break
                    
                time.sleep(1) # Wait for UI to settle before next check
                
            if cleared_count > 0:
                logger.info(f"✓ Cleared {cleared_count} vendors from previous sessions")
            else:
                logger.info("Supplier Cart appears empty")
                
        except Exception as e:
            logger.error(f"Error clearing supplier cart: {e}")



    


    def _parse_results(self, max_results: int) -> List[Dict[str, Any]]:
        """Parse vendor cards from search results page."""
        vendors = []
        
        try:
            # Try to extract from JSON-LD structured data
            # First check if there are ANY script tags on the page at all
            if self.page.locator('script').count() == 0:
                logger.warning("No script tags found on page, skipping JSON-LD")
                raise Exception("JSON-LD script not found")

            # Wait for the JSON-LD script with a shorter timeout
            try:
                self.page.wait_for_selector('script[type="application/ld+json"]', timeout=3000)
                logger.info("JSON-LD script tag found")
            except PlaywrightTimeoutError:
                logger.warning("JSON-LD script tag not found (3s timeout)")
                raise Exception("JSON-LD script not found")
            
            json_ld_locator = self.page.locator('script[type="application/ld+json"]')
            
            if json_ld_locator.count() > 0:
                import json
                import re
                
                logger.info(f"Found {json_ld_locator.count()} JSON-LD script tags")
                
                json_content = json_ld_locator.first.inner_text()
                logger.debug(f"JSON-LD content length: {len(json_content)} chars")
                
                data = json.loads(json_content)
                logger.debug(f"JSON-LD keys: {list(data.keys())}")
                
                # The structure is: {"@graph": [{"@id": "#search-results", "itemListElement": [...]}]}
                if "@graph" in data:
                    logger.info(f"Found @graph with {len(data['@graph'])} items")
                    
                    for item in data["@graph"]:
                        if item.get("@id") == "#search-results" and "itemListElement" in item:
                            vendor_list = item["itemListElement"]
                            
                            logger.info(f"Found {len(vendor_list)} vendors in JSON-LD data")
                            
                            for vendor_item in vendor_list[:max_results]:
                                vendor_data = vendor_item.get("item", {})
                                
                                # Extract address
                                address = vendor_data.get("address", {})
                                location = f"{address.get('addressLocality', '')}, {address.get('addressRegion', '')}"
                                location = location.strip(", ")
                                
                                vendor = {
                                    "name": vendor_data.get("name", "Unknown"),
                                    "profile_url": vendor_data.get("url", ""),
                                    "location": location,
                                    "address": {
                                        "street": address.get("streetAddress", ""),
                                        "city": address.get("addressLocality", ""),
                                        "state": address.get("addressRegion", ""),
                                        "zip": address.get("postalCode", ""),
                                        "country": address.get("addressCountry", "USA")
                                    },
                                    "website": vendor_data.get("sameAs", [""])[0] if vendor_data.get("sameAs") else "",
                                    "verified": False,  # Will need to check badges separately
                                    "rating": 0.0  # Not in JSON-LD, would need to scrape from page
                                }
                                
                                vendors.append(vendor)
                            
                            logger.info(f"Parsed {len(vendors)} vendors from JSON-LD")
                            return vendors
                    
                    logger.warning("No #search-results found in @graph")
                else:
                    logger.warning("No @graph found in JSON-LD data")
            else:
                logger.warning("JSON-LD locator count is 0")
            
            # Fallback: Try to parse from HTML cards if JSON-LD fails
            logger.warning("JSON-LD parsing failed, trying HTML card parsing...")
            
        except Exception as e:
            logger.error(f"JSON-LD parsing error: {e}", exc_info=True)
            logger.warning("Falling back to HTML card parsing...")


        
        # Fallback HTML parsing with updated 2026 selectors
        try:
            # Wait for list items containing supplier cards
            # Modern ThomasNet selector for search results
            self.page.wait_for_selector('li[data-sentry-component*="SearchResult"]', timeout=5000)
            logger.info("Page loaded, looking for vendor cards...")
        except PlaywrightTimeoutError:
            logger.warning("Modern selectors not found. Checking broad li elements...")
        
        # Updated selector strategy for current ThomasNet HTML structure
        # Prioritize specific sentry components, fallback to generic li
        card_selectors = [
            'li[data-sentry-component="SearchResultSupplier"]',
            'li[data-sentry-component*="SearchResult"]',
            '.SearchResultSupplier',
            '.supplier-card',
            'li:has(h2 button)'
        ]
        
        cards = []
        for selector in card_selectors:
            found = self.page.locator(selector).all()
            if found:
                cards = found
                logger.info(f"Found {len(cards)} items using selector: {selector}")
                break
        
        if not cards:
            logger.warning("No vendor cards found with any selector.")
            # Debug: Save HTML to inspect structure
            try:
                Path("logs").mkdir(exist_ok=True)
                with open("logs/no_vendors_debug.html", "w", encoding="utf-8") as f:
                    f.write(self.page.content())
                self.page.screenshot(path="logs/no_vendors_found.png")
            except:
                pass
            return []
        
        valid_cards = cards # Assume filtered by selector above
        logger.info(f"Parsing top {min(max_results, len(valid_cards))} vendors...")
        
        for i, card in enumerate(valid_cards[:max_results]):
            try:
                # Extract vendor name from h2 button (updated selector)
                name_elem = card.locator('h2 button').first
                name = name_elem.inner_text().strip() if name_elem.count() > 0 else f"Vendor {i+1}"
                
                # Extract website URL from "Visit Website" button
                website_elem = card.locator('a[class*="visitWebsiteButton"]').first
                website = website_elem.get_attribute('href') if website_elem.count() > 0 else ""
                
                # Extract profile URL - could be from "View Profile" button or the h2 button
                # The h2 button might have onclick navigation or data attributes
                profile_url = ""
                try:
                    # Try to get profile link from View Profile button
                    profile_btn = card.locator('button[class*="viewProfile"]').first
                    if profile_btn.count() > 0:
                        # Profile buttons typically navigate via JavaScript
                        # We'll construct the URL from the company name or look for data attributes
                        onclick = profile_btn.get_attribute('onclick') or ""
                        if '/company/' in onclick:
                            import re
                            match = re.search(r'/company/[^\'\"]+', onclick)
                            if match:
                                profile_url = f"https://www.thomasnet.com{match.group(0)}"
                except:
                    pass
                
                # If no profile URL found, try to extract from h2 button or other links
                if not profile_url:
                    link_elem = card.locator('a[href*="/company/"]').first
                    if link_elem.count() > 0:
                        profile_url = link_elem.get_attribute('href')
                        if profile_url and not profile_url.startswith('http'):
                            profile_url = f"https://www.thomasnet.com{profile_url}"
                
                # Extract location (typically shown with an icon)
                location = ""
                try:
                    # Location often appears near company info
                    location_text = card.locator('text=/[A-Z]{2}\\s+\\d{5}/').first
                    if location_text.count() > 0:
                        location = location_text.inner_text().strip()
                except:
                    # Fallback: try to find any text that looks like a location
                    try:
                        all_text = card.inner_text()
                        import re
                        location_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}\s+\d{5})', all_text)
                        if location_match:
                            location = location_match.group(1)
                    except:
                        pass
                
                # Check for manufacturer/distributor designation
                company_type = ""
                try:
                    type_elem = card.locator('text=/Manufacturer|Distributor/').first
                    if type_elem.count() > 0:
                        company_type = type_elem.inner_text().strip()
                except:
                    pass
                
                vendor = {
                    "name": name,
                    "profile_url": profile_url,
                    "website": website,
                    "location": location,
                    "company_type": company_type,
                    "verified": False,  # Would need specific badge detection
                    "rating": 0.0  # Not readily visible in card view
                }
                
                vendors.append(vendor)
                logger.info(f"✓ Parsed vendor {i+1}/{min(max_results, len(valid_cards))}: {name}")
                
            except Exception as e:
                logger.warning(f"Failed to parse vendor card {i}: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(vendors)} vendors from HTML")
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
