#!/usr/bin/env python3
"""
Merge Wholesale Pricing with Products Export (Fuzzy Matching)
Uses fuzzy string matching to better match product names.
"""

import csv
import os
from datetime import datetime
from difflib import SequenceMatcher

def similarity(a, b):
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_match(product_name, pricing_data, threshold=0.6):
    """Find the best matching product name in pricing data."""
    best_match = None
    best_score = 0
    
    for pricing_name in pricing_data.keys():
        score = similarity(product_name, pricing_name)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = pricing_name
    
    return best_match, best_score

def merge_pricing_data_fuzzy():
    """Merge wholesale pricing data with products export using fuzzy matching."""
    
    project_dir = "/Users/apple/Downloads/rebusinessautomationproject"
    
    # Read pricing data
    pricing_file = os.path.join(project_dir, "product_with.csv")
    products_file = os.path.join(project_dir, "products_export_20251205_221059.csv")
    
    print("=" * 80)
    print("MERGING WHOLESALE PRICING DATA (FUZZY MATCHING)")
    print("=" * 80)
    
    # Load pricing data into a dictionary
    pricing_data = {}
    with open(pricing_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_name = row['Product Name'].strip()
            pricing_data[product_name] = {
                'manufacturer': row['Manufacturer'],
                'wholesale_price': row['Estimated Wholesale Price']
            }
    
    print(f"\n✓ Loaded {len(pricing_data)} pricing records:")
    for name in pricing_data.keys():
        print(f"  - {name}")
    
    # Read products export
    products = []
    with open(products_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append(row)
    
    print(f"\n✓ Loaded {len(products)} products from export")
    
    # Create merged output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(project_dir, f"products_with_pricing_fuzzy_{timestamp}.csv")
    
    # Merge data with fuzzy matching
    exact_matches = 0
    fuzzy_matches = 0
    no_matches = 0
    
    print("\n" + "=" * 80)
    print("MATCHING PRODUCTS...")
    print("=" * 80)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'Product ID',
            'Product Name',
            'Manufacturer',
            'Estimated Wholesale Price',
            'Match Score',
            'Description',
            'Specifications',
            'Quantity',
            'NAICS Code',
            'Contract ID',
            'Solicitation Title',
            'Solicitation URL',
            'Location',
            'Date Added'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for product in products:
            product_name = product['Product Name'].strip()
            
            # Try exact match first
            manufacturer = ''
            wholesale_price = ''
            match_score = ''
            
            if product_name in pricing_data:
                manufacturer = pricing_data[product_name]['manufacturer']
                wholesale_price = pricing_data[product_name]['wholesale_price']
                match_score = '1.00 (Exact)'
                exact_matches += 1
            else:
                # Try fuzzy matching
                best_match, score = find_best_match(product_name, pricing_data, threshold=0.5)
                if best_match:
                    manufacturer = pricing_data[best_match]['manufacturer']
                    wholesale_price = pricing_data[best_match]['wholesale_price']
                    match_score = f'{score:.2f} (Fuzzy: {best_match})'
                    fuzzy_matches += 1
                    print(f"\n  Fuzzy Match ({score:.2f}):")
                    print(f"    Product: {product_name}")
                    print(f"    Matched: {best_match}")
                    print(f"    Mfg: {manufacturer}, Price: {wholesale_price}")
                else:
                    no_matches += 1
            
            # Write merged row
            writer.writerow({
                'Product ID': product['Product ID'],
                'Product Name': product['Product Name'],
                'Manufacturer': manufacturer,
                'Estimated Wholesale Price': wholesale_price,
                'Match Score': match_score,
                'Description': product['Description'],
                'Specifications': product['Specifications'],
                'Quantity': product['Quantity'],
                'NAICS Code': product['NAICS Code'],
                'Contract ID': product['Contract ID'],
                'Solicitation Title': product['Solicitation Title'],
                'Solicitation URL': product['Solicitation URL'],
                'Location': product['Location'],
                'Date Added': product['Date Added']
            })
    
    print("\n" + "=" * 80)
    print("MATCHING SUMMARY")
    print("=" * 80)
    print(f"  Exact matches: {exact_matches}")
    print(f"  Fuzzy matches: {fuzzy_matches}")
    print(f"  No matches: {no_matches}")
    print(f"  Total products: {len(products)}")
    
    print("\n" + "=" * 80)
    print(f"✅ MERGED FILE CREATED: {output_file}")
    print("=" * 80)
    
    return output_file

if __name__ == "__main__":
    output_file = merge_pricing_data_fuzzy()
    print(f"\n📊 Open the file to see all products with pricing data!")
    print(f"   File: {output_file}")
