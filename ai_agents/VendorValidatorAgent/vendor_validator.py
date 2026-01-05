
import os
import sys
import json
import logging
from typing import Dict, Any, Optional

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database_manager import DatabaseManager
from config import GEMINI_API_KEY

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VendorValidator")

class VendorValidatorAgent:
    """
    Agent to validate if a manufacturer/vendor is a good match for a specific solicitation/product
    based on their industry category and specialty.
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

    def is_sector_match(self, vendor_name: str, vendor_description: str, product_name: str, solicitation_title: str) -> bool:
        """
        Uses Gemini to determine if the vendor's line of business matches the product's sector.
        Returns True if it's a likely match, False if there's a clear mismatch (e.g. Bakery vs Aircraft).
        """
        if not self.model:
            # Fallback: simple keyword mismatch check if Gemini is unavailable
            mismatch_keywords = ["bakery", "food", "kitchen", "catering", "restaurant"]
            aircraft_keywords = ["aircraft", "bell crank", "flight", "aerospace", "aviation"]
            
            v_lower = vendor_name.lower() + " " + vendor_description.lower()
            p_lower = product_name.lower() + " " + solicitation_title.lower()
            
            if any(k in v_lower for k in mismatch_keywords) and any(k in p_lower for k in aircraft_keywords):
                logger.warning(f"Simple Check: Clear mismatch detected for {vendor_name} and {product_name}")
                return False
            return True

        prompt = f"""
        Analyze if the following vendor is a legitimate match for the given product/solicitation.
        We want to avoid sending technical aerospace or defense requests to unrelated companies (like food service, bakery, or retail).

        Vendor Name: {vendor_name}
        Vendor Description/Context: {vendor_description}

        Requested Product: {product_name}
        Solicitation Title: {solicitation_title}

        Rule: 
        - If the vendor is a bakery/food maker and the product is a mechanical aircraft part (like a Bell Crank, Pulley, etc.), return "MISMATCH".
        - If the vendor is clearly in a different sector (e.g. medical vs construction), return "MISMATCH".
        - If the vendor is a general distributor, machine shop, or relevant manufacturer, return "MATCH".
        - If unsure, return "MATCH".

        Return ONLY a JSON object with:
        "analysis": "Brief reasoning",
        "result": "MATCH" or "MISMATCH"
        """
        
        try:
            response = self.model.generate_content(prompt)
            # find JSON in response text
            import re
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                is_match = data.get("result") == "MATCH"
                if not is_match:
                    logger.warning(f"Validation failed for {vendor_name}: {data.get('analysis')}")
                return is_match
        except Exception as e:
            logger.error(f"Gemini validation error: {e}")
            
        return True # Default to True to avoid blocking if AI fails

    def validate_and_flag(self, vendor_id: int, product_id: int):
        """
        Validates a specific link in the database and updates its status.
        """
        # Fetch data
        conn = self.db._connect_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, website FROM manufacturers WHERE id = ?", (vendor_id,))
        m = cursor.fetchone()
        
        cursor.execute("SELECT product_name, contract_id FROM products WHERE id = ?", (product_id,))
        p = cursor.fetchone()
        
        if not m or not p:
            logger.warning(f"Could not find manufacturer {vendor_id} or product {product_id} to validate.")
            return None
            
        cursor.execute("SELECT title FROM solicitations WHERE contract_id = ?", (p['contract_id'],))
        s = cursor.fetchone()
        
        sol_title = s['title'] if s else ""
        
        # Simple description from name or website if we don't have a deeper crawl yet
        vendor_desc = m['website'] or ""
        
        # Determine match
        is_match = self.is_sector_match(m['name'], vendor_desc, p['product_name'], sol_title)
        
        # Update database
        status = "valid" if is_match else "invalid"
        notes = f"Validated by Gemini: {'Match' if is_match else 'Sector Mismatch'}"
        
        self.db.update_supplier_validation(product_id, vendor_id, status, notes)
        
        if not is_match:
            logger.warning(f"!!! DISCOVERED MISMATCH: {m['name']} is NOT a good match for {p['product_name']}. Status set to 'invalid'.")
        else:
            logger.info(f"Confirmed match: {m['name']} for {p['product_name']}.")
            
        return is_match

if __name__ == "__main__":
    validator = VendorValidatorAgent()
    # Test case: Foodmaker vs Bell Crank
    result = validator.is_sector_match(
        "Food Makers Bakery Equipment", 
        "Official Site: https://www.bakeryequipment.net/Default.asp - Industrial bakery equipment and ovens.",
        "Bell Crank",
        "Bell Crank for SIKORSKY AIRCRAFT"
    )
    print(f"Validation Result (Foodmaker vs Bell Crank): {'MATCH' if result else 'MISMATCH'}")
