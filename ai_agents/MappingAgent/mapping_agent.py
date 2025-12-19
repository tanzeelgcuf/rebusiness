from urllib.parse import urljoin, urlparse
import os
import sys
import re
import json
import time
from serpapi import GoogleSearch
import requests
from requests.exceptions import RequestException, HTTPError, ConnectionError
from bs4 import BeautifulSoup

# --- SELENIUM DEPENDENCIES ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- CONFIG & DEPENDENCY STUBS ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    import config
    import googlemaps
    from database_manager import DatabaseManager
    import google.generativeai as genai
    from openai import OpenAI
except ImportError as e:
    print(f"Error importing dependencies. Ensure config.py, database_manager.py, and required libraries are installed: {e}")
    # Define placeholder classes/variables if imports fail to allow script inspection
    class DatabaseManager:
        def __init__(self): pass
        def add_vendor(self, *args): print(f"DB Action: Adding vendor {args[1]}")
    config = type('Config', (object,), {'LLM_PROVIDER': 'gemini', 'GOOGLE_MAPS_API_KEY': 'STUB', 'SERPAPI_KEY': 'STUB', 'GEMINI_API_KEY': 'STUB', 'OPENAI_API_KEY': 'STUB'})
    googlemaps = type('GoogleMaps', (object,), {'Client': lambda key: type('Client', (object,), {'places': lambda query, **kwargs: {'results': []}})})
    genai = type('Gemini', (object,), {'configure': lambda key: None, 'GenerativeModel': lambda model: type('Model', (object,), {'generate_content': lambda prompt: type('Response', (object,), {'text': 'Vendor A, Vendor B'})})})
    OpenAI = lambda api_key: type('Client', (object,), {'chat': type('Chat', (object,), {'completions': type('Completions', (object,), {'create': lambda **kwargs: type('Response', (object,), {'choices': [{'message': type('Message', (object,), {'content': 'Vendor A, Vendor B'})}]})})})})
    if __name__ == '__main__': raise

# --- REVISED MAPPING AGENT WITH SELENIUM ---

class MappingAgent:
    """
    Finds and analyzes commercial vendors, using Selenium for deep crawling 
    to extract emails and verify government capabilities.
    """
    
    GOVERNMENT_DOMAINS = [
        # ... (list remains the same) ...
        ".gov", ".mil", "dla.mil", "redriver.army.mil", "army.mil", "navy.mil",
        "airforce.mil", "marines.mil", "uscg.mil", "dod.mil", "nasa.gov",
        "energy.gov", "epa.gov", "gsa.gov", "nih.gov", "va.gov", "usda.gov",
        "doc.gov", "treas.gov", "state.gov", "justice.gov", "doi.gov",
        "dot.gov", "hud.gov", "ed.gov", "opm.gov", "ssa.gov",
        "fbi.gov", "cia.gov", "nsa.gov", "irs.gov", "usa.gov", "dot.gov",
        "usps.com"
    ]
    
    COMMON_NOISE_SUFFIXES = ['llc', 'inc', 'corp', 'ltd', 'lp', 'co']

    def __init__(self):
        self.gmaps = googlemaps.Client(key=config.GOOGLE_MAPS_API_KEY)
        self.db_manager = DatabaseManager()
        
        # Configure LLM clients
        if config.LLM_PROVIDER == "gemini":
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.llm_model = 'gemini-2.5-pro'
        elif config.LLM_PROVIDER == "openai":
            self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
            self.llm_model = 'gpt-4o-mini'

        # --- SELENIUM INITIALIZATION ---
        self.driver = self._initialize_driver()

    def _initialize_driver(self):
        """Initializes the Selenium WebDriver in headless mode."""
        print("Initializing Chrome WebDriver for MappingAgent...")
        chrome_options = Options()
        chrome_options.add_argument("--headless=new") 
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        # Add a common user agent to reduce bot detection risk
        chrome_options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(20) # Shorter timeout for efficiency
            print("WebDriver initialized successfully for MappingAgent.")
            return driver
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            raise

    def close(self):
        """Closes the Selenium driver."""
        if self.driver:
            self.driver.quit()
            print("WebDriver for MappingAgent closed.")
        print("MappingAgent closed.")

    def _is_government_website(self, url):
        """Checks if a given URL belongs to a known government domain."""
        if not url: return False
        parsed_url = urlparse(url).netloc.lower()
        for domain in self.GOVERNMENT_DOMAINS:
            if domain in parsed_url:
                return True
        return False

    def _google_search_for_website_selenium(self, vendor_name):
        """Fallback to a direct Google search using Selenium if APIs fail."""
        print(f"  - Using Selenium to Google search for '{vendor_name}' website.")
        try:
            search_query = f'"{vendor_name}" official website'
            self.driver.get(f"https://www.google.com/search?q={search_query}")
            
            # Handle cookie consent if present
            try:
                consent_button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept all') or contains(text(), 'I agree')]"))
                )
                consent_button.click()
                print("    - Clicked Google consent button.")
            except TimeoutException:
                pass # No consent banner found

            # Wait for search results to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "search"))
                )
            except TimeoutException:
                print("    - Search results container 'id=search' not found.")
                self.driver.save_screenshot(f"google_search_fail_{vendor_name.replace(' ', '_')}.png")
                return None, None
            
            search_results = self.driver.find_elements(By.XPATH, "//div[@id='search']//div[@class='g']//a")
            
            if not search_results:
                 search_results = self.driver.find_elements(By.CSS_SELECTOR, 'div.g a')

            for result in search_results[:5]:
                try:
                    link = result.get_attribute('href')
                    if link:
                        if not any(domain in link for domain in ['google.com', 'wikipedia.org', 'facebook.com', 'linkedin.com', 'youtube.com']) and not self._is_government_website(link):
                            print(f"    - Found potential website via Selenium search: {link}")
                            return link, None
                except StaleElementReferenceException:
                    continue

        except Exception as e:
            print(f"    - Selenium Google search failed for '{vendor_name}': {e}")
            self.driver.save_screenshot(f"google_search_error_{vendor_name.replace(' ', '_')}.png")
            
        return None, None
        
    def _get_emails_from_text(self, text):
        """Extracts email addresses from a given text string."""
        return set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))

    def _detect_email_pattern(self, emails, domain):
        """
        Detects the email naming pattern from a list of emails.
        Returns the most common pattern type.
        """
        if not emails:
            return None
        
        patterns = {
            'first.last': 0,
            'firstlast': 0,
            'flast': 0,
            'first': 0,
            'f.last': 0
        }
        
        for email in emails:
            if '@' not in email or domain not in email:
                continue
            
            local_part = email.split('@')[0].lower()
            
            # Detect pattern
            if '.' in local_part:
                parts = local_part.split('.')
                if len(parts) == 2:
                    if len(parts[0]) > 1 and len(parts[1]) > 1:
                        patterns['first.last'] += 1
                    elif len(parts[0]) == 1 and len(parts[1]) > 1:
                        patterns['f.last'] += 1
            else:
                # No dot in email
                # Check if it's single letter + lastname (flast pattern)
                if len(local_part) > 2:
                    # Heuristic: if 4-8 chars and starts with single letter, likely flast
                    # e.g., jdoe, jsmith
                    if 3 <= len(local_part) <= 8:
                        patterns['flast'] += 1
                    elif len(local_part) > 8:
                        # Longer emails without dots are likely firstlast
                        patterns['firstlast'] += 1
                    else:
                        # Very short, likely just first name
                        patterns['first'] += 1
        
        # Return most common pattern
        if max(patterns.values()) == 0:
            return 'first.last'  # Default fallback
        
        return max(patterns, key=patterns.get)

    def _extract_names_from_website(self, soup):
        """
        Extracts person names from website content.
        Looks for Team, About, Leadership sections.
        """
        names = []
        
        # Look for common sections containing names
        name_sections = soup.find_all(['div', 'section'], class_=re.compile(r'team|about|staff|leadership|people|our-team', re.I))
        
        # Also check for specific tags
        if not name_sections:
            name_sections = soup.find_all(['h3', 'h4', 'h5', 'p'], string=re.compile(r'^[A-Z][a-z]+ [A-Z][a-z]+$'))
        
        for section in name_sections[:10]:  # Limit to avoid processing too much
            text = section.get_text()
            # Find names in format: "FirstName LastName"
            # Simple pattern: Two capitalized words
            name_matches = re.findall(r'\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b', text)
            
            for first, last in name_matches:
                # Filter out common false positives
                if first.lower() not in ['the', 'our', 'about', 'contact', 'learn', 'more'] and \
                   last.lower() not in ['the', 'our', 'about', 'contact', 'learn', 'more', 'team', 'page']:
                    names.append({'first': first.lower(), 'last': last.lower()})
        
        # Remove duplicates
        unique_names = []
        seen = set()
        for name in names:
            key = f"{name['first']}_{name['last']}"
            if key not in seen:
                seen.add(key)
                unique_names.append(name)
        
        return unique_names[:10]  # Limit to 10 names

    def _generate_email_from_pattern(self, first_name, last_name, domain, pattern):
        """
        Generates an email address using a detected pattern.
        """
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        
        if pattern == 'first.last':
            return f"{first}.{last}@{domain}"
        elif pattern == 'firstlast':
            return f"{first}{last}@{domain}"
        elif pattern == 'flast':
            return f"{first[0]}{last}@{domain}"
        elif pattern == 'f.last':
            return f"{first[0]}.{last}@{domain}"
        elif pattern == 'first':
            return f"{first}@{domain}"
        else:
            return f"{first}.{last}@{domain}"  # Default

    def _extract_emails_from_page_source(self, page_source, soup=None):
        """
        Advanced email extraction from HTML source.
        Handles obfuscated emails, JSON-LD, meta tags, and various encoding schemes.
        """
        emails = set()
        
        # 1. Standard regex extraction
        standard_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_source)
        emails.update(standard_emails)
        
        # 2. Obfuscated patterns: "email [at] domain [dot] com"
        obfuscated_pattern = r'([a-zA-Z0-9._%+-]+)\s*(?:\[at\]|@|\(at\))\s*([a-zA-Z0-9.-]+)\s*(?:\[dot\]|\.|\.|\(dot\))\s*([a-zA-Z]{2,})'
        for match in re.finditer(obfuscated_pattern, page_source, re.IGNORECASE):
            email = f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
            emails.add(email.replace(' ', ''))
        
        if soup:
            # 3. Check meta tags
            for meta in soup.find_all('meta'):
                content = meta.get('content', '')
                if '@' in content:
                    meta_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
                    emails.update(meta_emails)
            
            # 4. Parse JSON-LD structured data
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        # Look for email in Organization schema
                        if data.get('@type') == 'Organization':
                            if 'email' in data:
                                emails.add(data['email'])
                            if 'contactPoint' in data:
                                contact = data['contactPoint']
                                if isinstance(contact, dict) and 'email' in contact:
                                    emails.add(contact['email'])
                except:
                    pass
            
            # 5. Check footer sections (common location for contact info)
            for footer in soup.find_all(['footer', 'div'], class_=re.compile(r'footer|contact', re.I)):
                footer_text = footer.get_text()
                footer_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', footer_text)
                emails.update(footer_emails)
        
        # 6. Decode HTML entities (&commat; = @)
        decoded_source = page_source.replace('&commat;', '@').replace('&#64;', '@')
        decoded_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', decoded_source)
        emails.update(decoded_emails)
        
        # Filter out common false positives
        filtered_emails = set()
        for email in emails:
            email_lower = email.lower()
            # Skip placeholder/example emails
            if any(skip in email_lower for skip in ['example.com', 'test.com', 'domain.com', 'email.com', 'yourcompany.com']):
                continue
            # Skip image/asset URLs that look like emails
            if any(ext in email_lower for ext in ['.png', '.jpg', '.gif', '.svg', '.css', '.js']):
                continue
            filtered_emails.add(email)
        
        return filtered_emails

    def _get_place_details(self, place_id):
        """
        Gets detailed information about a business using Google Places API.
        Returns email, rating, review count, and other details.
        """
        try:
            place_details = self.gmaps.place(
                place_id,
                fields=['name', 'formatted_phone_number', 'website', 'rating', 
                       'user_ratings_total', 'type', 'business_status']
            )
            
            result = place_details.get('result', {})
            
            # Try to extract email from website or other fields
            # Note: Google doesn't directly provide email in API, but we can check website
            details = {
                'website': result.get('website'),
                'phone': result.get('formatted_phone_number'),
                'rating': result.get('rating', 0),
                'review_count': result.get('user_ratings_total', 0),
                'types': result.get('type', []),  # Note: API returns 'type' but we store as 'types'
                'business_status': result.get('business_status', 'OPERATIONAL'),
                'email': None  # Will be extracted via deep crawl
            }
            
            return details
            
        except Exception as e:
            print(f"    - Error getting place details: {e}")
            return None

    def _extract_email_from_google_profile(self, place_id, business_name):
        """
        Extract email from Google Business Profile by checking reviews and descriptions.
        """
        try:
            # Get place details with reviews
            place_details = self.gmaps.place(
                place_id,
                fields=['name', 'reviews', 'editorial_summary', 'website']
            )
            
            result = place_details.get('result', {})
            found_emails = set()
            
            # 1. Check editorial summary
            editorial_summary = result.get('editorial_summary', {})
            if isinstance(editorial_summary, dict):
                summary_text = editorial_summary.get('overview', '')
                if summary_text:
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', summary_text)
                    found_emails.update(emails)
            
            # 2. Check business owner responses to reviews
            reviews = result.get('reviews', [])
            for review in reviews[:10]:  # Check first 10 reviews
                # Check owner response
                if 'author_name' in review and review.get('author_name') == business_name:
                    response_text = review.get('text', '')
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', response_text)
                    found_emails.update(emails)
            
            if found_emails:
                # Prioritize business-related emails
                priority_emails = [e for e in found_emails if any(role in e.lower() for role in ['info@', 'contact@', 'sales@', 'support@'])]
                return priority_emails[0] if priority_emails else list(found_emails)[0]
                
        except Exception as e:
            print(f"    - Error extracting email from Google profile: {e}")
        
        return None

    def _filter_vendor_names(self, vendor_names):
        """
        Filters out government entities, duplicates, and invalid vendor names.
        """
        filtered = []
        seen = set()
        
        # Generic terms to exclude
        generic_terms = {
            'inc', 'inc.', 'llc', 'llc.', 'corp', 'corp.', 'ltd', 'ltd.', 
            'company', 'co', 'co.', 'corporation', 'incorporated',
            'ace', 'the', 'and', 'or', 'for', 'with', 'from'
        }
        
        for name in vendor_names:
            if not name:
                continue
                
            name_lower = name.lower().strip()
            
            # Skip if it's just a generic term
            if name_lower in generic_terms:
                continue
            
            # Skip very short names (likely acronyms or incomplete)
            if len(name) < 3:
                continue
                
            # Skip government entities
            gov_keywords = ['dla', 'defense logistics agency', 'government', 'federal', 
                           'department of', 'u.s.', 'united states', 'navy', 'army', 
                           'air force', 'marines', 'coast guard']
            if any(keyword in name_lower for keyword in gov_keywords):
                continue
            
            # Avoid duplicates (case-insensitive)
            if name_lower not in seen:
                seen.add(name_lower)
                filtered.append(name)
        
        return filtered

    def _llm_generate_vendors(self, product_details, delivery_location_obj, naics_code):
        """Uses an LLM to generate potential commercial vendor names."""
        # ... (implementation remains the same as in the previous rewrite) ...
        vendors = set()
        product_strings = []
        for p in product_details:
            prod_str = f"{p.get('quantity', '')} {p.get('unit', '')} of {p.get('name', '')}"
            if p.get('part_number'):
                prod_str += f", Part No. {p.get('part_number')}"
            product_strings.append(prod_str.strip())
        
        products_info = ", ".join(product_strings)

        location_parts = [delivery_location_obj.get(k) for k in ['city', 'state'] if delivery_location_obj.get(k)]
        location_str = ", ".join(location_parts) if location_parts else "an unspecified location"

        prompt = f"""
        Given the following product requirements and delivery location, suggest up to 10 actual, **commercial** vendors (manufacturers or distributors). Focus on well-known companies likely to supply these specific products.

        **IMPORTANT: Do NOT suggest government entities (e.g., DLA, Army Depots, federal/state entities).**

        Product Requirements: {products_info}
        Delivery Location: {location_str}
        NAICS Code: {naics_code or "Not specified"}

        Provide only a comma-separated list of actual vendor names. Do NOT include any additional text or formatting.
        Example: "Acme Corp, Global Supplies Inc, Tech Solutions LLC"
        """
        try:
            if config.LLM_PROVIDER == "gemini":
                model = genai.GenerativeModel(self.llm_model)
                response = model.generate_content(prompt)
                text = response.text
            elif config.LLM_PROVIDER == "openai":
                response = self.openai_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200
                )
                text = response.choices[0].message.content

            generated_vendors = [v.strip() for v in text.split(',') if v.strip()]
            
            filtered_vendors = [v for v in generated_vendors if not any(gov_keyword in v.lower() for gov_keyword in ['dla', 'defense logistics agency', 'army depot', 'indian health service', 'federal government'])]
            
            return self._filter_vendor_names(filtered_vendors)
            
        except Exception as e:
            print(f"    - LLM vendor generation failed: {e}")
            return []

    def _find_website_and_linkedin(self, vendor_name):
        """Uses SerpAPI to find the official website and LinkedIn URL."""
        website_url = None
        linkedin_url = None

        try:
            params = {
                "q": f'"{vendor_name}" website',
                "api_key": config.SERPAPI_KEY,
                "hl": "en",
                "gl": "us"
            }
            search = GoogleSearch(params)
            results = search.get_dict().get("organic_results", [])
            
            candidates = []
            for r in results[:5]:
                link = r.get('link')
                if not link: continue
                
                if 'linkedin.com/company/' in link and not linkedin_url:
                    linkedin_url = link
                    continue

                if self._is_government_website(link) or 'facebook.com' in link or 'linkedin.com' in link:
                    continue

                score = 0
                if vendor_name.lower() in r.get('title', '').lower():
                    score += 2
                if vendor_name.lower() in link:
                    score += 1
                
                candidates.append({'url': link, 'score': score})

            if candidates:
                # Sort by score, descending
                candidates.sort(key=lambda x: x['score'], reverse=True)
                website_url = candidates[0]['url']
                    
            print(f"  - Initial Search -> Website: {website_url or 'None'}, LinkedIn: {linkedin_url or 'None'}")
            return website_url, linkedin_url
            
        except Exception as e:
            print(f"    - SerpAPI website search failed for '{vendor_name}': {e}. Check key/limits.")
            return None, None

    def _google_search_for_website_selenium(self, vendor_name):
        """Fallback to a direct Google search using Selenium if APIs fail."""
        print(f"  - Using Selenium to Google search for '{vendor_name}' website.")
        try:
            search_query = f'"{vendor_name}" official website'
            self.driver.get(f"https://www.google.com/search?q={search_query}")
            
            print(f"    - Page Title: {self.driver.title}")

            # Handle cookie consent if present
            try:
                consent_button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept all') or contains(text(), 'I agree')]"))
                )
                consent_button.click()
                print("    - Clicked Google consent button.")
            except TimeoutException:
                pass # No consent banner found

            # Wait for search results to load
            # Try multiple selectors for results container
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "search"))
                )
            except TimeoutException:
                print("    - Search results container 'id=search' not found.")
                # Check if we are on a captcha page or something else
                if "sorry" in self.driver.current_url:
                    print("    - Detected Google 'We're sorry' (Captcha) page.")
                
                # Save screenshot and source for debugging
                self.driver.save_screenshot(f"google_search_fail_{vendor_name.replace(' ', '_')}.png")
                with open(f"google_search_fail_{vendor_name.replace(' ', '_')}.html", "w") as f:
                    f.write(self.driver.page_source)
                # Don't return here, let it fall through to fallback
                # return None, None
            
            # Find all search result links using robust selectors
            # Look for h3 headers which usually contain the link title, then get the parent anchor
            search_results = self.driver.find_elements(By.XPATH, "//div[@id='search']//div[@class='g']//a")
            
            if not search_results:
                 # Fallback selector
                 search_results = self.driver.find_elements(By.CSS_SELECTOR, 'div.g a')

            for result in search_results[:5]:
                try:
                    link = result.get_attribute('href')
                    if link:
                        # Basic filtering of non-vendor links
                        if not any(domain in link for domain in ['google.com', 'wikipedia.org', 'facebook.com', 'linkedin.com', 'youtube.com']) and not self._is_government_website(link):
                            print(f"    - Found potential website via Selenium search: {link}")
                            return link, None # No reliable way to get LinkedIn URL here
                except StaleElementReferenceException:
                    continue

        except Exception as e:
            print(f"    - Selenium Google search failed for '{vendor_name}': {e}")
            self.driver.save_screenshot(f"google_search_error_{vendor_name.replace(' ', '_')}.png")
        
        print(f"    - Google search failed. Attempting DuckDuckGo fallback for '{vendor_name}'.")
        return self._duckduckgo_search_for_website_selenium(vendor_name)

    def _duckduckgo_search_for_website_selenium(self, vendor_name):
        """Fallback to DuckDuckGo search."""
        print(f"  - Using Selenium to DuckDuckGo search for '{vendor_name}' website.")
        try:
            search_query = f'"{vendor_name}" official website'
            # Use standard DuckDuckGo
            self.driver.get(f"https://duckduckgo.com/?q={search_query}&t=h_&ia=web")
            
            print(f"    - DDG Page Title: {self.driver.title}")

            # Wait for results
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='result-title-a']"))
                )
            except TimeoutException:
                print("    - DDG Search results not found.")
                self.driver.save_screenshot(f"ddg_search_fail_{vendor_name.replace(' ', '_')}.png")
                return None, None
            
            search_results = self.driver.find_elements(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
            
            for result in search_results[:5]:
                try:
                    link = result.get_attribute('href')
                    if link:
                        if not any(domain in link for domain in ['duckduckgo.com', 'wikipedia.org', 'facebook.com', 'linkedin.com', 'youtube.com']) and not self._is_government_website(link):
                            print(f"    - Found potential website via DuckDuckGo search: {link}")
                            return link, None
                except StaleElementReferenceException:
                    continue
                    
        except Exception as e:
            print(f"    - Selenium DuckDuckGo search failed for '{vendor_name}': {e}")
            self.driver.save_screenshot(f"ddg_search_error_{vendor_name.replace(' ', '_')}.png")
            
        return None, None

    def _llm_analyze_gov_experience(self, vendor_name):
        """Performs a Google search via SerpAPI and uses an LLM to analyze results."""
        # ... (implementation remains the same as in the previous rewrite) ...
        summary = {"agencies": [], "summary": "No past performance found."}
        
        try:
            params = {
                "q": f'"{vendor_name}" AND ("government contract" OR "CAGE code" OR "SAM.gov" OR "past performance")',
                "api_key": config.SERPAPI_KEY,
                "hl": "en",
                "gl": "us"
            }
            search = GoogleSearch(params)
            results = search.get_dict()
        except Exception as e:
            print(f"    - SerpAPI government experience search failed: {e}. Check key/limits.")
            return summary
            
        if not results.get("organic_results"):
            return summary

        search_snippets = [f"Title: {r.get('title', '')}\nSnippet: {r.get('snippet', '')}" for r in results["organic_results"][:5]]
        llm_content = "\n---\n".join(search_snippets)

        prompt = f"""
        Analyze the following Google search results for "{vendor_name}" to determine past government contracting experience.
        Search Results:
        {llm_content}
        
        Return your analysis as a JSON object with two keys: 
        1. "agencies": A list of specific government agency names mentioned (e.g., "VA", "DoD", "Army").
        2. "summary": A one-sentence summary of their government contracting experience based *only* on the text provided.
        
        If no experience is evident, return empty list for agencies and "No past performance found." for the summary.
        """
        
        try:
            if config.LLM_PROVIDER == "gemini":
                model = genai.GenerativeModel(self.llm_model, generation_config={"response_mime_type": "application/json"})
                response = model.generate_content(prompt)
                return json.loads(response.text)
            elif config.LLM_PROVIDER == "openai":
                response = self.openai_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    max_tokens=500
                )
                return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"    - LLM analysis failed: {e}. Returning default summary.")
            return summary
            
    def _calculate_confidence_score(self, vendor_name, website_url, has_email, gov_agencies, agency_target, has_gov_page, google_rating=0, google_review_count=0):
        """Calculates a score based on data quality and relevance."""
        score = 0
        
        # Base Score for Data Quality
        if website_url:
            score += 15
        if has_email:
            score += 20
        if has_gov_page:
            score += 15 # Found a dedicated 'government' or 'contract' page

        # Relevance Score (Past Performance)
        if gov_agencies:
            score += 30 # Strong evidence of past performance
            
            # Check for specific agency match (e.g., VA)
            if agency_target and any(agency_target.lower() in a.lower() for a in gov_agencies):
                score += 20 # Direct experience with the target agency
        
        # Google Rating Bonuses (NEW)
        if google_rating >= 4.5:
            score += 10  # Excellent rating
        elif google_rating >= 4.0:
            score += 5   # Good rating
        
        if google_review_count >= 50:
            score += 5   # Well-established business
        elif google_review_count >= 20:
            score += 3   # Decent review count
            
        return min(int(score), 100)

    def _get_relevant_page_urls(self, base_url, soup):
        """Finds URLs for 'Contact', 'About', 'Government', etc. pages."""
        relevant_urls = set()
        keywords = ['contact', 'about', 'service', 'support', 'government', 'contracts', 'team', 'locations', 'offices', 'connect', 'reach']
        
        priority_links = []
        other_links = []

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            link_text = link.text.lower()
            
            # Basic checks for relevance
            is_relevant = any(keyword in link_text for keyword in keywords) or any(keyword in href for keyword in keywords)
            
            if is_relevant:
                # Resolve relative URLs
                full_url = urljoin(base_url, link.get('href'))
                # Only follow links on the same domain
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    if "contact" in link_text or "contact" in href or "support" in link_text or "support" in href:
                         priority_links.append(full_url)
            else:
                         other_links.append(full_url)
        
        # Prioritize contact pages
        all_links = priority_links + other_links
        return list(dict.fromkeys(all_links))[:10]  # Increased from 5 to 10 pages, remove duplicates
        
    def _deep_crawl_vendor(self, vendor_name, website_url, agency_target):
        """
        Uses Selenium to crawl the website for emails and government keywords.
        This function replaces the simpler `_find_website_and_contact` for email extraction.
        """
        details = {
            "email": None, 
            "has_gov_page": False, 
            "key_personnel": [],
            "linkedin_url": None, # Will be set by the initial search
            "all_text": "" # For optional keyword scoring later
        }

        found_emails = set()
        
        # Use an original window to minimize multi-tab complexity
        # NOTE: If this agent runs in a loop, ensure the driver is clean before starting.
        
        try:
            print(f"  - Deep crawling vendor website: {website_url}")
            self.driver.get(website_url)
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2) # Small delay to mimic human behavior
            
            main_page_source_lower = self.driver.page_source.lower()
            details["all_text"] += main_page_source_lower
            
            # Use enhanced email extraction
            soup = BeautifulSoup(self.driver.page_source, 'html.parser') # Use original case for soup to find mailto links correctly
            found_emails.update(self._extract_emails_from_page_source(main_page_source_lower, soup))

            # Check for government keywords on the main page
            if "government" in main_page_source_lower or "contract" in main_page_source_lower or agency_target.lower() in main_page_source_lower:
                details["has_gov_page"] = True

            # Get links to crawl next
            relevant_links = self._get_relevant_page_urls(website_url, soup)
            
            for link_url in relevant_links:
                try:
                    print(f"    - Crawling relevant page: {link_url}")
                    self.driver.get(link_url)
                    WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    time.sleep(1) # Small delay
                    
                    page_source_lower = self.driver.page_source.lower()
                    details["all_text"] += page_source_lower
                    
                    # Use enhanced email extraction
                    sub_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    found_emails.update(self._extract_emails_from_page_source(page_source_lower, sub_soup))
                    
                    if "government" in page_source_lower or "contracts" in page_source_lower or agency_target.lower() in page_source_lower:
                        details["has_gov_page"] = True
                        
                except Exception as e:
                    print(f"    - Error crawling {link_url}: {e}")
                    continue

            # Select the best email
            if found_emails:
                priority_emails = [e for e in found_emails if any(role in e for role in ['sales@', 'info@', 'contact@', 'support@', 'gov@'])]
                details["email"] = priority_emails[0] if priority_emails else (list(found_emails)[0] if found_emails else None)
            
            # PATTERN DETECTION: If we found emails, try to generate more
            domain = urlparse(website_url).netloc.replace("www.", "")
            if found_emails and len(found_emails) >= 1:
                print(f"    - Attempting pattern-based email generation...")
                pattern = self._detect_email_pattern(found_emails, domain)
                if pattern:
                    print(f"    - Detected email pattern: {pattern}")
                    
                    # Extract names from the website
                    # Re-parse with original case for name extraction
                    original_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    names = self._extract_names_from_website(original_soup)
                    
                    if names:
                        print(f"    - Found {len(names)} potential employee names")
                        generated_emails = set()
                        for name in names:
                            generated_email = self._generate_email_from_pattern(
                                name['first'], name['last'], domain, pattern
                            )
                            generated_emails.add(generated_email)
                        
                        # Add generated emails to found_emails
                        found_emails.update(generated_emails)
                        print(f"    - Generated {len(generated_emails)} additional emails using pattern")
                        
                        # Update best email if we don't have one yet
                        if not details["email"] and generated_emails:
                            # Prefer sales/contact from generated emails
                            priority_generated = [e for e in generated_emails if any(role in e for role in ['sales', 'contact', 'info'])]
                            details["email"] = priority_generated[0] if priority_generated else list(generated_emails)[0]
            
            # Fallback 1: Search Dorking
            if not details["email"]:
                print(f"    - No email found via crawling. Attempting Search Dorking...")
                domain = urlparse(website_url).netloc.replace("www.", "")
                dork_email = self._search_dorking_for_email(vendor_name, domain)
                if dork_email:
                    details["email"] = dork_email
                    print(f"    - Found email via Search Dorking: {dork_email}")

            # Fallback 2: LinkedIn Company Page Search
            if not details["email"]:
                print(f"    - No email found via Dorking. Searching LinkedIn...")
                linkedin_email = self._search_linkedin_company_page(vendor_name)
                if linkedin_email:
                    details["email"] = linkedin_email
                    print(f"    - Found email via LinkedIn: {linkedin_email}")

            # Fallback 3: WHOIS Domain Lookup
            if not details["email"]:
                print(f"    - No email found via LinkedIn. Trying WHOIS lookup...")
                domain = urlparse(website_url).netloc.replace("www.", "")
                whois_email = self._whois_domain_lookup(domain)
                if whois_email:
                    details["email"] = whois_email
                    print(f"    - Found email via WHOIS: {whois_email}")

            # Fallback 4: Common Alias Guessing
            if not details["email"]:
                print(f"    - No email found via Dorking. Generating common aliases...")
                domain = urlparse(website_url).netloc.replace("www.", "")
                aliases = self._guess_common_aliases(domain)
                # We can't verify these without sending, so we'll just pick the most likely one (sales) or store them all.
                # For now, let's pick 'sales' as the primary and maybe store others if the DB supported it.
                # But the system expects a single email string.
                details["email"] = aliases[0] # sales@domain.com
                print(f"    - Using guessed alias: {details['email']}")

        except (TimeoutException, WebDriverException) as e:
            print(f"  - Error/Timeout crawling main vendor website {website_url} with Selenium: {e}")
        except Exception as e:
            print(f"  - An unexpected error occurred while processing vendor website {website_url}: {e}")
            
        return details

    def _search_dorking_for_email(self, vendor_name, domain):
        """
        Uses DuckDuckGo to search for emails associated with the domain.
        Query: site:domain.com "@domain.com"
        """
        try:
            search_query = f'site:{domain} "@{domain}"'
            print(f"    - Dorking query: {search_query}")
            
            self.driver.get(f"https://duckduckgo.com/?q={search_query}&t=h_&ia=web")
            
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='result-title-a']"))
                )
            except TimeoutException:
                print("    - Dorking search returned no results.")
                return None

            # Extract text from results to find emails
            page_source = self.driver.page_source.lower()
            found_emails = self._get_emails_from_text(page_source)
            
            # Filter for emails belonging to the domain
            valid_emails = [e for e in found_emails if domain in e]
            
            if valid_emails:
                # Prioritize common roles
                priority_emails = [e for e in valid_emails if any(role in e for role in ['sales@', 'info@', 'contact@', 'support@'])]
                return priority_emails[0] if priority_emails else valid_emails[0]
                
        except Exception as e:
            print(f"    - Error during Search Dorking: {e}")
            
        return None

    def _search_linkedin_company_page(self, company_name):
        """
        Search for company email via LinkedIn company page.
        """
        try:
            search_query = f'site:linkedin.com/company "{company_name}"'
            print(f"    - LinkedIn search: {search_query}")
            
            self.driver.get(f"https://duckduckgo.com/?q={search_query}&t=h_&ia=web")
            
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='result-title-a']"))
                )
            except TimeoutException:
                return None
            
            # Get first LinkedIn company page result
            results = self.driver.find_elements(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
            
            for result in results[:2]:
                try:
                    link = result.get_attribute('href')
                    if link and 'linkedin.com/company/' in link:
                        # Visit LinkedIn page
                        self.driver.get(link)
                        time.sleep(2)
                        
                        page_source = self.driver.page_source
                        # Look for emails in page source
                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_source)
                        
                        if emails:
                            # Filter for business emails (not LinkedIn emails)
                            business_emails = [e for e in emails if 'linkedin.com' not in e.lower()]
                            if business_emails:
                                return business_emails[0]
                except:
                    continue
                    
        except Exception as e:
            print(f"    - Error during LinkedIn search: {e}")
        
        return None

    def _whois_domain_lookup(self, domain):
        """
        Extract contact email from WHOIS domain registration data.
        """
        try:
            import whois
            
            print(f"    - WHOIS lookup for: {domain}")
            w = whois.whois(domain)
            
            # Try to get registrant, admin, or tech email
            potential_emails = []
            
            if hasattr(w, 'emails'):
                if isinstance(w.emails, list):
                    potential_emails.extend(w.emails)
                elif w.emails:
                    potential_emails.append(w.emails)
            
            # Filter out privacy protection emails
            valid_emails = []
            for email in potential_emails:
                if email and isinstance(email, str):
                    email_lower = email.lower()
                    # Skip privacy/proxy emails
                    if not any(skip in email_lower for skip in ['privacy', 'proxy', 'whoisguard', 'protected', 'redacted']):
                        valid_emails.append(email)
            
            if valid_emails:
                return valid_emails[0]
                
        except ImportError:
            print(f"    - WHOIS library not installed. Run: pip install python-whois")
        except Exception as e:
            print(f"    - WHOIS lookup failed: {e}")
        
        return None
    
    def _guess_common_aliases(self, domain):
        """Generates common email aliases for a given domain."""
        aliases = [
            f"sales@{domain}",
            f"info@{domain}",
            f"contact@{domain}",
            f"support@{domain}"
        ]
        return aliases


    def find_vendors(self, contract_id, analysis_summary):
        """
        Finds, analyzes, and saves commercial vendors.
        """
        delivery_location_obj = analysis_summary.get('delivery_location', {})
        product_details = analysis_summary.get('product_details', [])
        naics_code = analysis_summary.get('naics_code')
        agency_target = analysis_summary.get('agency', '')

        if not product_details or not delivery_location_obj:
            print("Missing product or location details. Skipping vendor search.")
            return
            
        location_str = ' '.join(filter(None, [
            delivery_location_obj.get('city', ''),
            delivery_location_obj.get('state', '')
        ])).strip()

        print(f"--- Starting Vendor Search for contract {contract_id} in {location_str} ---")

        # 1. LLM-powered vendor generation (High-quality list)
        llm_suggested_vendors = self._llm_generate_vendors(product_details, delivery_location_obj, naics_code)
        all_vendor_names = set(llm_suggested_vendors)
        print(f"  - LLM Suggested Vendors: {len(all_vendor_names)}")
        
        # 2. Google Maps Search (Local relevance) - ENHANCED
        product_keywords_for_search = list(set([p.get('name') for p in product_details if p.get('name')]))[:3]  # Top 3 keywords
        
        unique_places = {}
        acceptable_business_types = {'store', 'point_of_interest', 'establishment', 'hardware_store', 
                                    'home_goods_store', 'electronics_store', 'furniture_store'}
        excluded_business_types = {'restaurant', 'food', 'cafe', 'bar', 'lodging', 'school', 
                                   'hospital', 'church', 'gym', 'spa'}
        
        # Multi-keyword search
        for keyword in product_keywords_for_search:
            query = f'"{keyword}" supplier in {location_str}'
            
            # Add NAICS code if available for better relevance
            if naics_code:
                query += f' NAICS {naics_code}'
            
            print(f"  - Google Maps search: {query}")
            try:
                places_result = self.gmaps.places(query=query, region='us', language='en-US')
                
                for place in places_result.get('results', []):
                    place_id = place.get('place_id')
                    name = place.get('name')
                    
                    # Skip if already processed
                    if place_id in unique_places:
                        continue
                    
                    # Skip government entities
                    if name and any(gov_keyword in name.lower() for gov_keyword in ['dla', 'defense logistics agency']):
                        continue
                    
                    # Get detailed information
                    place_details = self._get_place_details(place_id)
                    
                    if not place_details:
                        continue
                    
                    # Apply rating filter (3.5+ stars, 5+ reviews)
                    rating = place_details.get('rating', 0)
                    review_count = place_details.get('review_count', 0)
                    
                    if rating < 3.5 and review_count >= 5:
                        print(f"    - Skipping {name}: Low rating ({rating})")
                        continue
                    
                    # Business type validation
                    place_types = set(place_details.get('types', []))
                    
                    # Skip excluded types
                    if place_types & excluded_business_types:
                        print(f"    - Skipping {name}: Excluded business type")
                        continue
                    
                    # Check business status
                    if place_details.get('business_status') != 'OPERATIONAL':
                        print(f"    - Skipping {name}: Not operational")
                        continue
                    
                    # Skip government websites
                    website = place_details.get('website')
                    if website and self._is_government_website(website):
                        continue
                    
                    # Try to extract email from Google Business Profile
                    google_email = self._extract_email_from_google_profile(place_id, name)
                    
                    # Add to unique places with enhanced details
                    unique_places[place_id] = {
                        'name': name,
                        'website': website,
                        'phone': place_details.get('phone'),
                        'rating': rating,
                        'review_count': review_count,
                        'types': list(place_types),
                        'google_email': google_email  # Email from Google Business Profile
                    }
                    all_vendor_names.add(name)
                    
            except Exception as e:
                print(f"  - Google Maps API error for '{keyword}': {e}")
        
        print(f"  - Found {len(unique_places)} businesses from Google Maps")

        
        final_vendor_list = self._filter_vendor_names(list(all_vendor_names))
        print(f"--- Found {len(final_vendor_list)} unique and filtered potential vendors ---")

        for vendor_name in final_vendor_list:
            
            # Get existing Maps data if available
            place_data = next((p for p in unique_places.values() if p.get('name') == vendor_name), {})
            website_url = place_data.get('website')
            phone_number = place_data.get('phone')
            place_types = place_data.get('types', [])
            google_rating = place_data.get('rating', 0)
            google_review_count = place_data.get('review_count', 0)
            google_email = place_data.get('google_email') # NEW: Email from Google Business Profile
            
            linkedin_url = None
            
            print(f"\n--- Analyzing vendor: {vendor_name} ---")
            if google_rating:
                print(f"  - Google Rating: {google_rating} ({google_review_count} reviews)")
            
            # --- Tier 1: Find Website/LinkedIn (SerpAPI) ---
            if not website_url:
                website_url, linkedin_url = self._find_website_and_linkedin(vendor_name)

            # --- Fallback: Selenium Google Search ---
            if not website_url:
                website_url, linkedin_url = self._google_search_for_website_selenium(vendor_name)
                
            # If still no website, we cannot proceed with deep crawl
            if not website_url:
                print(f"  - Skipping deep crawl: No reliable website found for {vendor_name}.")
                # Use Google email if we have it
                website_details = {"email": google_email, "has_gov_page": False}
            else:
                # --- Tier 2: Deep Crawl for Email and Gov Keywords (Selenium) ---
                website_details = self._deep_crawl_vendor(vendor_name, website_url, agency_target)
                
                # If deep crawl didn't find email but we have Google email, use it
                if not website_details.get('email') and google_email:
                    website_details['email'] = google_email
                    print(f"  - Using email from Google Business Profile: {google_email}")
                
            # --- Tier 3: Analyze Past Government Experience (SerpAPI + LLM) ---
            past_performance_analysis = self._llm_analyze_gov_experience(vendor_name)
            
            # --- Tier 4: Calculate Final Score and Save ---
            confidence_score = self._calculate_confidence_score(
                vendor_name, 
                website_url, 
                bool(website_details['email']), 
                past_performance_analysis["agencies"], 
                agency_target,
                website_details['has_gov_page'],
                google_rating,
                google_review_count
            )

            self.db_manager.add_vendor(
                contract_id=contract_id, 
                name=vendor_name, 
                website=website_url, 
                email=website_details['email'], 
                phone=phone_number, 
                confidence_score=confidence_score, 
                has_gov_page=website_details['has_gov_page'], 
                has_past_performance=bool(past_performance_analysis["agencies"]),
                gov_agencies_worked_with=json.dumps(past_performance_analysis["agencies"]),
                past_performance_summary=past_performance_analysis["summary"],
                key_personnel=json.dumps([]),
                linkedin_url=linkedin_url,
                place_types=json.dumps(place_types)
            )

# --- EXAMPLE USAGE (for testing) ---

if __name__ == '__main__':
    # ... (Example usage section remains the same for testing purposes) ...
    test_contract_id_1 = "TEST_VISN17_GENEXPERT"
    test_analysis_1 = {
        'title': 'VISN 17 GeneXpert Analyzer M&R Consolidated IDIQ',
        'agency': 'VA',
        'naics_code': '811219',
        'delivery_location': {
            'city': 'Multiple Locations within VISN 17', 'state': 'TX', 'zip_code': ''
        },
        'product_details': [
            {'name': 'GeneXpert Infinity Service Agreement', 'unit': 'YR', 'quantity': '1', 'part_number': 'GX-INF-SA'},
            {'name': 'GX 16-16 Advantage Service Agreement', 'unit': 'YR', 'quantity': '3', 'part_number': 'GX-16-16-SA'}
        ]
    }
    
    test_contract_id_2 = "TEST_MERIDIAN_MAINTENANCE"
    test_analysis_2 = {
        'title': 'MERIDIAN IV MICROSCOPE MAINTENANCE',
        'agency': 'NAVY',
        'naics_code': '334516',
        'delivery_location': {
            'street': '300 HIGHWAY 361', 'city': 'CRANE', 'state': 'IN', 'zip_code': '47522'
        },
        'product_details': [
            {'name': 'MERIDIAN IV MICROSCOPE MAINTENACE', 'unit': 'Lot', 'quantity': '1', 'part_number': '1119015'},
            {'name': 'CW-LVP 12.5 GHz Oscillo', 'unit': 'Lot', 'quantity': '1', 'part_number': '1119286'}
        ]
    }
    
    mapping_agent = MappingAgent()
    try:
        # Run test 1
        print("\n" + "="*80)
        print(f"STARTING TEST 1: {test_analysis_1['title']}")
        print("="*80)
        mapping_agent.find_vendors(test_contract_id_1, test_analysis_1)
        
        # Run test 2
        print("\n" + "="*80)
        print(f"STARTING TEST 2: {test_analysis_2['title']}")
        print("="*80)
        mapping_agent.find_vendors(test_contract_id_2, test_analysis_2)
        
    finally:
        mapping_agent.close()