import logging
import os
from typing import Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class RFQSummarizer:
    """
    Generates concise RFQ summaries for vendor forms using Gemini.
    """
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            logger.warning("No Google API Key found. Summarizer will use fallback templates.")
            self.model = None

    def generate_summary(self, rfq_data: Dict[str, Any], product: Dict[str, Any]) -> str:
        """
        Generate a summary text for the RFQ form.
        
        Args:
            rfq_data: Full RFQ data from parser
            product: Specific product being sourced
            
        Returns:
            Concise summary string (max ~500 chars usually)
        """
        if self.model:
            try:
                return self._generate_with_ai(rfq_data, product)
            except Exception as e:
                logger.error(f"AI generation failed: {e}")
                return self._generate_fallback(rfq_data, product)
        else:
            return self._generate_fallback(rfq_data, product)

    def _generate_with_ai(self, rfq_data: Dict[str, Any], product: Dict[str, Any]) -> str:
        """Use Gemini to generate summary."""
        product_name = product.get("name", "Information")
        qty = product.get("quantity", "Unknown")
        specs = product.get("specifications", {})
        deadline = rfq_data.get("metadata", {}).get("deadline", "ASAP")
        
        prompt = f"""
        Write a concise, professional RFQ message (max 500 chars) for a vendor inquiry.
        
        Product: {product_name}
        Quantity: {qty}
        Specifications: {specs}
        Deadline: {deadline}
        Context: We are Camp Sable, LLC, a government contractor.
        
        Keep it direct. Mention we are looking for a quote.
        """
        
        response = self.model.generate_content(prompt)
        return response.text.replace("\n", " ").strip()

    def _generate_fallback(self, rfq_data: Dict[str, Any], product: Dict[str, Any]) -> str:
        """Template-based fallback summary."""
        product_name = product.get("name", "Product")
        qty = product.get("quantity", "specified")
        deadline = rfq_data.get("metadata", {}).get("deadline", "ASAP")
        
        return (
            f"RFQ for {product_name}. Quantity: {qty}. "
            f"Camp Sable, LLC is requesting a quote for this item. "
            f"Please review the attached RFQ document for full specifications. "
            f"Response needed by {deadline}. "
            f"Thank you."
        )

if __name__ == "__main__":
    # Test
    summ = RFQSummarizer()
    data = {"metadata": {"deadline": "2026-02-01"}}
    prod = {"name": "Industrial Bolts", "quantity": 500, "specifications": {"Material": "Steel"}}
    print(summ.generate_summary(data, prod))
