"""
Manufacturer Discovery Agent
Finds US-based manufacturers for products extracted from government solicitations.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import re
from database_manager import DatabaseManager

class ManufacturerAgent:
    def __init__(self):
        self.db = DatabaseManager()
        self.driver = None
        
    def _init_driver(self):
        """Initialize Selenium WebDriver."""
        if self.driver is None:
            print("Initializing Chrome WebDriver for ManufacturerAgent...")
            options = webdriver.ChromeOptions()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
            self.driver = webdriver.Chrome(options=options)
            print("WebDriver initialized successfully.")
    
    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            print("WebDriver closed.")
    
    def find_manufacturers(self, product_name, product_specs=None, naics_code=None):
        """
        Find US-based manufacturers for a specific product.
        
        Args:
            product_name: Name of the product
            product_specs: Product specifications (optional)
            naics_code: NAICS industry code (optional)
            
        Returns:
            List of manufacturer dictionaries
        """
        print(f"\n--- Finding manufacturers for: {product_name} ---")
        manufacturers = []
        
        # Strategy 1: Google Search
        google_manufacturers = self._google_search_manufacturers(product_name, product_specs)
        manufacturers.extend(google_manufacturers)
        
        # Strategy 2: ThomasNet Search (if available)
        # thomasnet_manufacturers = self._thomasnet_search(product_name)
        # manufacturers.extend(thomasnet_manufacturers)
        
        # Remove duplicates based on name
        unique_manufacturers = {}
        for mfg in manufacturers:
            if mfg['name'] not in unique_manufacturers:
                unique_manufacturers[mfg['name']] = mfg
        
        print(f"Found {len(unique_manufacturers)} unique manufacturers.")
        return list(unique_manufacturers.values())
    
    def _google_search_manufacturers(self, product_name, product_specs=None):
        """Search DuckDuckGo for manufacturers (more reliable than Google)."""
        manufacturers = []
        
        try:
            self._init_driver()
            
            # Build search query
            search_query = f'"{product_name}" manufacturer USA'
            if product_specs:
                search_query += f' {product_specs}'
            
            print(f"  - DuckDuckGo search: {search_query}")
            
            # Use DuckDuckGo instead of Google (more reliable)
            search_url = f"https://duckduckgo.com/?q={search_query}&t=h_&ia=web"
            
            # Set page load timeout to avoid hanging
            self.driver.set_page_load_timeout(30)
            
            try:
                self.driver.get(search_url)
            except Exception as e:
                print(f"  - Page load timeout or error: {e}")
                print(f"  - Trying to continue anyway...")
            
            time.sleep(4)  # Give page time to render
            
            # Wait for results to load
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='result'], ol.react-results--main li"))
                )
            except TimeoutException:
                print("  - Timeout waiting for search results")
                # Try alternative selector
                try:
                    results = self.driver.find_elements(By.CSS_SELECTOR, "li[data-layout='organic']")
                    if results:
                        print(f"  - Found {len(results)} results with alternative selector")
                except:
                    # Take screenshot for debugging
                    self.driver.save_screenshot("/tmp/manufacturer_search_debug.png")
                    print("  - Screenshot saved to /tmp/manufacturer_search_debug.png")
                    return manufacturers
            
            # Extract search results - try multiple selectors
            try:
                # Try primary selector
                results = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='result']")
                
                # If no results, try alternative selectors
                if not results:
                    results = self.driver.find_elements(By.CSS_SELECTOR, "li[data-layout='organic']")
                
                if not results:
                    results = self.driver.find_elements(By.CSS_SELECTOR, "ol.react-results--main li")
                
                print(f"  - Found {len(results)} search results")
                
                if len(results) == 0:
                    print("  - No results found. Saving debug screenshot...")
                    self.driver.save_screenshot("/tmp/manufacturer_search_debug.png")
                    return manufacturers
                
                for i, result in enumerate(results[:15], 1):  # Top 15 results
                    try:
                        # Try multiple selectors for title and link
                        title = None
                        url = None
                        
                        # Try primary selectors
                        try:
                            title_elem = result.find_element(By.CSS_SELECTOR, "h2")
                            title = title_elem.text
                        except:
                            try:
                                title_elem = result.find_element(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
                                title = title_elem.text
                            except:
                                try:
                                    title_elem = result.find_element(By.CSS_SELECTOR, "h2 a, .result__title a")
                                    title = title_elem.text
                                except:
                                    continue
                        
                        # Get URL
                        try:
                            link_elem = result.find_element(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
                            url = link_elem.get_attribute('href')
                        except:
                            try:
                                link_elem = result.find_element(By.CSS_SELECTOR, "h2 a, .result__title a")
                                url = link_elem.get_attribute('href')
                            except:
                                continue
                        
                        if not title or not url:
                            continue
                        
                        print(f"    [{i}] Title: {title[:60]}...")
                        print(f"        URL: {url[:80]}...")
                        
                        # Extract company name from title
                        company_name = self._extract_company_name(title)
                        
                        if company_name and url:
                            # Verify it's a manufacturer (not a marketplace/distributor)
                            if self._is_likely_manufacturer(title, url):
                                manufacturers.append({
                                    'name': company_name,
                                    'website': url,
                                    'source': 'DuckDuckGo Search'
                                })
                                print(f"        ✓ Added: {company_name}")
                            else:
                                print(f"        ✗ Filtered out (marketplace/directory)")
                        else:
                            print(f"        ✗ Skipped (no valid company name)")
                    except Exception as e:
                        print(f"    [{i}] Error parsing result: {e}")
                        continue
                        
            except Exception as e:
                print(f"  - Error extracting search results: {e}")
        
        except Exception as e:
            print(f"  - Error during search: {e}")
        
        return manufacturers
    
    def _extract_company_name(self, title):
        """Extract company name from search result title."""
        # Remove common suffixes
        title = re.sub(r'\s*[-|–]\s*.*$', '', title)
        
        # Remove "Inc", "LLC", "Corp" etc. from end for cleaner name
        # But keep them in the actual stored name
        company_name = title.strip()
        
        # Filter out generic terms
        generic_terms = ['manufacturer', 'supplier', 'distributor', 'wholesale', 'products']
        if any(term in company_name.lower() for term in generic_terms) and len(company_name.split()) <= 2:
            return None
        
        return company_name if len(company_name) > 3 else None
    
    def _is_likely_manufacturer(self, title, url):
        """Check if the result is likely a manufacturer (not a marketplace)."""
        # Exclude marketplaces and directories
        excluded_domains = [
            'amazon.com', 'ebay.com', 'alibaba.com', 'aliexpress.com',
            'walmart.com', 'target.com', 'homedepot.com', 'lowes.com',
            'thomasnet.com', 'globalspec.com', 'indiamart.com',
            'wikipedia.org', 'youtube.com'
        ]
        
        for domain in excluded_domains:
            if domain in url.lower():
                return False
        
        # Look for manufacturer keywords
        manufacturer_keywords = ['manufacturer', 'manufacturing', 'made in usa', 'factory', 'producer']
        if any(keyword in title.lower() for keyword in manufacturer_keywords):
            return True
        
        return True  # Default to True if no exclusions matched
    
    def get_manufacturer_contact_info(self, manufacturer_name, website):
        """
        Scrape manufacturer website for contact information.
        
        Args:
            manufacturer_name: Name of the manufacturer
            website: Manufacturer website URL
            
        Returns:
            Dictionary with contact info (email, phone, address)
        """
        print(f"\n  - Getting contact info for: {manufacturer_name}")
        contact_info = {
            'email': None,
            'phone': None,
            'address': None,
            'city': None,
            'state': None,
            'zip_code': None
        }
        
        try:
            self._init_driver()
            self.driver.get(website)
            time.sleep(2)
            
            # Look for contact page
            try:
                contact_link = self.driver.find_element(By.XPATH, 
                    "//a[contains(translate(., 'CONTACT', 'contact'), 'contact')]")
                contact_url = contact_link.get_attribute('href')
                self.driver.get(contact_url)
                time.sleep(2)
            except:
                pass  # Stay on main page if no contact link
            
            page_source = self.driver.page_source
            
            # Extract email
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_source)
            if emails:
                # Prioritize sales/info emails
                priority_emails = [e for e in emails if any(role in e.lower() for role in ['sales', 'info', 'contact', 'wholesale'])]
                contact_info['email'] = priority_emails[0] if priority_emails else emails[0]
            
            # Extract phone
            phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', page_source)
            if phones:
                contact_info['phone'] = phones[0]
            
            # Extract address (basic pattern)
            # This is simplified - could be enhanced with more sophisticated parsing
            address_pattern = r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln)'
            addresses = re.findall(address_pattern, page_source, re.IGNORECASE)
            if addresses:
                contact_info['address'] = addresses[0]
            
            # Extract state (look for 2-letter state codes)
            states = re.findall(r'\b([A-Z]{2})\b', page_source)
            us_states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
                        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
                        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
                        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
            
            for state in states:
                if state in us_states:
                    contact_info['state'] = state
                    break
            
            print(f"    - Email: {contact_info['email']}")
            print(f"    - Phone: {contact_info['phone']}")
            print(f"    - State: {contact_info['state']}")
            
        except Exception as e:
            print(f"    - Error getting contact info: {e}")
        
        return contact_info
    
    def save_manufacturer(self, manufacturer_data):
        """Save manufacturer to database."""
        return self.db.add_manufacturer(
            name=manufacturer_data['name'],
            website=manufacturer_data.get('website'),
            email=manufacturer_data.get('email'),
            phone=manufacturer_data.get('phone'),
            address=manufacturer_data.get('address'),
            city=manufacturer_data.get('city'),
            state=manufacturer_data.get('state'),
            zip_code=manufacturer_data.get('zip_code'),
            is_us_based=True
        )

if __name__ == "__main__":
    # Test the agent
    agent = ManufacturerAgent()
    
    # Test product
    manufacturers = agent.find_manufacturers("GeneXpert Analyzer", "molecular diagnostic system")
    
    # Get contact info for first manufacturer
    if manufacturers:
        mfg = manufacturers[0]
        contact_info = agent.get_manufacturer_contact_info(mfg['name'], mfg['website'])
        mfg.update(contact_info)
        
        # Save to database
        mfg_id = agent.save_manufacturer(mfg)
        print(f"\nSaved manufacturer with ID: {mfg_id}")
    
    agent.close()
