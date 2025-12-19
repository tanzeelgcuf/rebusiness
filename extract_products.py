#!/usr/bin/env python3
"""
Product Extractor
Extracts product information from solicitations already in the database.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database_manager import DatabaseManager
import json
import re

class ProductExtractor:
    def __init__(self):
        self.db = DatabaseManager()
    
    def extract_products_from_solicitations(self):
        """Extract products from all solicitations in the database."""
        print("=" * 80)
        print("EXTRACTING PRODUCTS FROM SOLICITATIONS")
        print("=" * 80)
        
        # Get all solicitations
        conn = self.db._connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT contract_id, title, analysis_summary FROM solicitations WHERE analysis_summary IS NOT NULL")
        solicitations = cursor.fetchall()
        self.db._close_db()
        
        print(f"\nFound {len(solicitations)} solicitations with analysis.")
        
        products_extracted = 0
        
        for sol in solicitations:
            contract_id = sol['contract_id']
            title = sol['title']
            analysis = sol['analysis_summary']
            
            print(f"\n--- Processing: {contract_id} ---")
            print(f"Title: {title}")
            
            # Extract products from analysis
            products = self._parse_products_from_analysis(analysis, title)
            
            if products:
                print(f"Found {len(products)} product(s):")
                for product in products:
                    print(f"  - {product['name']}")
                    
                    # Save to database
                    product_id = self.db.add_product(
                        contract_id=contract_id,
                        product_name=product['name'],
                        description=product.get('description'),
                        specifications=product.get('specifications'),
                        quantity=product.get('quantity'),
                        naics_code=product.get('naics_code')
                    )
                    
                    if product_id:
                        products_extracted += 1
            else:
                print("  - No products identified")
        
        print("\n" + "=" * 80)
        print(f"EXTRACTION COMPLETE: {products_extracted} products extracted")
        print("=" * 80)
        
        return products_extracted
    
    def _parse_products_from_analysis(self, analysis, title):
        """
        Parse product information from the analysis summary.
        
        Args:
            analysis: Analysis summary text
            title: Solicitation title
            
        Returns:
            List of product dictionaries
        """
        products = []
        
        try:
            # Clean analysis text (strip markdown)
            clean_analysis = analysis.strip()
            if clean_analysis.startswith('```json'):
                clean_analysis = clean_analysis[7:]
            if clean_analysis.startswith('```'):
                clean_analysis = clean_analysis[3:]
            if clean_analysis.endswith('```'):
                clean_analysis = clean_analysis[:-3]
            clean_analysis = clean_analysis.strip()
            
            # Try to parse as JSON first
            if clean_analysis.startswith('{'):
                data = json.loads(clean_analysis)
                
                # Look for products in various fields
                if 'products' in data:
                    for product in data['products']:
                        products.append(self._normalize_product(product))
                
                elif 'product_requirements' in data:
                    # Parse product requirements
                    req = data['product_requirements']
                    if isinstance(req, dict):
                        products.append({
                            'name': req.get('name', title),
                            'description': req.get('description'),
                            'specifications': req.get('specifications'),
                            'quantity': req.get('quantity')
                        })
                    elif isinstance(req, str):
                        # Extract from text
                        products.append({
                            'name': title,
                            'description': req,
                            'specifications': None,
                            'quantity': self._extract_quantity(req)
                        })
                
                # If no products found, use title as product name
                if not products and 'summary' in data:
                    products.append({
                        'name': title,
                        'description': data['summary'],
                        'specifications': None,
                        'quantity': None
                    })
        
        except json.JSONDecodeError:
            # If not JSON, treat as plain text
            # Extract product name from title
            products.append({
                'name': self._clean_product_name(title),
                'description': analysis[:500] if len(analysis) > 500 else analysis,
                'specifications': None,
                'quantity': self._extract_quantity(analysis)
            })
        
        return products
    
    def _normalize_product(self, product):
        """Normalize product dictionary."""
        if isinstance(product, str):
            return {
                'name': product,
                'description': None,
                'specifications': None,
                'quantity': None
            }
        
        return {
            'name': product.get('name', product.get('product_name', 'Unknown Product')),
            'description': product.get('description'),
            'specifications': product.get('specifications', product.get('specs')),
            'quantity': product.get('quantity', product.get('qty'))
        }
    
    def _clean_product_name(self, title):
        """Clean product name from solicitation title."""
        # Remove common prefixes
        title = re.sub(r'^(Request for|RFQ|RFP|Solicitation for|Purchase of)\s+', '', title, flags=re.IGNORECASE)
        
        # Remove contract numbers and codes
        title = re.sub(r'\b[A-Z0-9]{10,}\b', '', title)
        
        # Remove extra whitespace
        title = ' '.join(title.split())
        
        return title.strip()
    
    def _extract_quantity(self, text):
        """Extract quantity from text."""
        # Look for patterns like "10 units", "Quantity: 5", etc.
        patterns = [
            r'quantity[:\s]+(\d+)',
            r'(\d+)\s+units?',
            r'(\d+)\s+pieces?',
            r'qty[:\s]+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None
    
    def list_all_products(self):
        """List all products currently in the database."""
        print("\n" + "=" * 80)
        print("PRODUCTS IN DATABASE")
        print("=" * 80)
        
        conn = self.db._connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, s.title as solicitation_title 
            FROM products p
            LEFT JOIN solicitations s ON p.contract_id = s.contract_id
            ORDER BY p.created_at DESC
        """)
        products = cursor.fetchall()
        self.db._close_db()
        
        if not products:
            print("\nNo products found in database.")
            return []
        
        print(f"\nTotal products: {len(products)}\n")
        
        for i, product in enumerate(products, 1):
            print(f"{i}. {product['product_name']}")
            print(f"   Contract: {product['contract_id']}")
            if product['solicitation_title']:
                print(f"   Solicitation: {product['solicitation_title']}")
            if product['quantity']:
                print(f"   Quantity: {product['quantity']}")
            if product['description']:
                desc = product['description'][:100] + "..." if len(product['description']) > 100 else product['description']
                print(f"   Description: {desc}")
            print()
        
        return [dict(p) for p in products]

if __name__ == "__main__":
    extractor = ProductExtractor()
    
    # Extract products from solicitations
    extractor.extract_products_from_solicitations()
    
    # List all products
    products = extractor.list_all_products()
    
    print(f"\n✅ Extraction complete! {len(products)} products ready for manufacturer search.")
