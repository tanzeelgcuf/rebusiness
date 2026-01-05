
import os
import sys
import json
import time
import re
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database_manager import DatabaseManager
from config import GEMINI_API_KEY

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DeepSpecAgent")

class DeepSpecAgent:
    """
    Agent to research NSNs and extract deep technical specifications from online databases.
    """
    
    def __init__(self):
        self.db = DatabaseManager()
        self.model = None
        if GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                self.model = genai.GenerativeModel('gemini-2.5-flash-image') # Migrated for higher quota
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}")

    def research_nsn(self, nsn: str) -> Dict[str, str]:
        """
        Research an NSN and return a dictionary of its technical characteristics.
        """
        logger.info(f"Researching deep specs for NSN: {nsn}")
        
        # Format NSN for search (remove dashes if needed, but often search works with them)
        search_query = f"NSN {nsn} characteristics specifications"
        
        # 1. Try Direct URL Construction (Faste & More Reliable)
        nsn_clean = nsn.replace("-", "")
        direct_urls = [
            f"https://www.parttarget.com/{nsn}.html",
            f"https://www.iso-group.com/NSN/{nsn}"
        ]
        
        for url in direct_urls:
            logger.info(f"  Trying direct URL: {url}")
            content = self._scrape_page(url)
            if content and ("Characteristics" in content or "technical data" in content.lower()):
                logger.info(f"  Successfully extracted data from direct URL: {url}")
                return self._extract_characteristics_with_ai(content, nsn)

        # 2. Fallback to Search
        try:
            from duckduckgo_search import DDGS
            results = list(DDGS().text(search_query, max_results=5))
        except Exception as e:
            logger.error(f"Search failed for {nsn}: {e}")
            return {}

        # Technical sites to prioritize
        tech_sites = ["parttarget.com", "iso-group.com", "nsncenter.com", "eznsn.com", "parts66.com"]
        
        target_url = None
        for res in results:
            href = res['href']
            if any(site in href for site in tech_sites):
                target_url = href
                break
        
        if not target_url and results:
            target_url = results[0]['href'] # Fallback to first result

        if target_url:
            logger.info(f"  Found technical page: {target_url}")
            # Scrape the page
            page_content = self._scrape_page(target_url)
            if page_content:
                characteristics = self._extract_characteristics_with_ai(page_content, nsn)
        
        return characteristics

    def _scrape_page(self, url: str) -> Optional[str]:
        """Scrapes a page using Playwright for robust content extraction."""
        from playwright.sync_api import sync_playwright
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                # Wait a bit for tables to render
                time.sleep(2)
                content = page.content()
                browser.close()
                return content
        except Exception as e:
            logger.error(f"Scrape failed for {url}: {e}")
            return None

    def _extract_characteristics_with_ai(self, html: str, nsn: str) -> Dict[str, str]:
        """Uses Gemini to parse technical tables from HTML into a clean JSON."""
        # Clean HTML to reduce token usage
        soup = BeautifulSoup(html, 'html.parser')
        # Look for tables or divs with technical data
        tech_data = ""
        for table in soup.find_all('table'):
            tech_data += table.get_text(separator=' ', strip=True) + "\n"
        
        if len(tech_data) < 100:
             # Try grabbing the main body if tables are missing
             main_body = soup.find('body')
             if main_body:
                 tech_data = main_body.get_text(separator=' ', strip=True)[:10000] # Cap it
        
        if not self.model:
            return {"raw_data": tech_data[:500]}

        prompt = f"""
        Extract detailed technical specifications and characteristics for NSN {nsn} from the following text.
        We need high-precision technical data to help a manufacturer quote accurately.
        
        Please extract:
        - Material (e.g., Aluminum Alloy 7075, Steel)
        - Finish/Surface Treatment (e.g., Anodized, Cadmium Plated)
        - Physical Dimensions (Length, Width, Height, Diameter, Thickness, Weight)
        - Thread Specifications (Size, Pitch, Class)
        - Technical Features (Hole diameter, number of holes, flange shape)
        - Application/End Item (What platform is this for?)
        - Cross-Reference Part Numbers & Manufacturer Names (CAGE Codes)

        Text:
        {tech_data[:8000]}

        Return ONLY a clean JSON object of key-value pairs. 
        Use descriptive keys (e.g., "Material", "Overall Length", "Thread Size").
        If no characteristics are found, return an empty object {{}}.
        """
        
        try:
            response = self.model.generate_content(prompt)
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                # Remove empty values
                return {k: v for k, v in data.items() if v and str(v).lower() not in ['n/a', 'none', 'unknown']}
        except Exception as e:
            logger.error(f"AI parsing failed for {nsn}: {e}")
            
        return {}

    def format_specs_for_email(self, specs_dict: Dict[str, str]) -> str:
        """Formats the specs dictionary into a clean, professional string for emails."""
        if not specs_dict:
            return ""
        
        lines = []
        for key, value in specs_dict.items():
            # Clean up key (e.g., "overall_length" -> "Overall Length")
            formatted_key = key.replace("_", " ").title()
            lines.append(f"{formatted_key}: {value}")
        
        return " | ".join(lines)

    def enrich_product_specs(self, product_id: int):
        """
        Main entry point to update a product with deep specs.
        """
        conn = self.db._connect_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT specifications, product_name FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if not row: return
        
        specs_text = row['specifications'] or ""
        # Find NSN in existing specs via regex
        nsn_match = re.search(r"(\d{4}-\d{2}-\d{3}-\d{4})", specs_text)
        if not nsn_match:
             # Try without dashes
             nsn_match = re.search(r"(\d{13})", specs_text)
             
        if not nsn_match:
            logger.warning(f"No NSN found in specs for Product ID {product_id}")
            return
            
        nsn = nsn_match.group(1)
        deep_specs = self.research_nsn(nsn)
        
        if deep_specs:
            # Format deep specs as a string using our helper
            deep_specs_str = self.format_specs_for_email(deep_specs)
            
            # Update product
            new_specs = f"{specs_text} | DEEP SPECS: {deep_specs_str}"
            cursor.execute("UPDATE products SET specifications = ? WHERE id = ?", (new_specs, product_id))
            conn.commit()
            logger.info(f"Successfully enriched Product ID {product_id} with deep specs.")
            return True
            
        return False

if __name__ == "__main__":
    agent = DeepSpecAgent()
    # Test case: Bell Crank NSN
    test_nsn = "3040-01-325-7874"
    results = agent.research_nsn(test_nsn)
    print(f"Deep Specs for {test_nsn}:")
    print(json.dumps(results, indent=2))
