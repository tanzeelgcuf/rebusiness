#!/usr/bin/env python3
"""
Create a summary CSV showing only products with manufacturer pricing data.
"""

import csv
import os

def create_pricing_summary():
    """Create a summary CSV with only products that have pricing data."""
    
    project_dir = "/Users/apple/Downloads/rebusinessautomationproject"
    input_file = os.path.join(project_dir, "products_with_pricing_fuzzy_20251205_232218.csv")
    output_file = os.path.join(project_dir, "products_with_pricing_SUMMARY.csv")
    
    products_with_pricing = []
    
    # Read the merged file
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Only include rows with manufacturer data
            if row['Manufacturer'].strip():
                products_with_pricing.append(row)
    
    # Write summary file
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'Product ID',
            'Product Name',
            'Manufacturer',
            'Estimated Wholesale Price',
            'Match Score',
            'Quantity',
            'Solicitation URL'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for product in products_with_pricing:
            writer.writerow({
                'Product ID': product['Product ID'],
                'Product Name': product['Product Name'],
                'Manufacturer': product['Manufacturer'],
                'Estimated Wholesale Price': product['Estimated Wholesale Price'],
                'Match Score': product['Match Score'],
                'Quantity': product['Quantity'],
                'Solicitation URL': product['Solicitation URL']
            })
    
    print("=" * 80)
    print("PRICING SUMMARY")
    print("=" * 80)
    print(f"\nProducts with manufacturer pricing: {len(products_with_pricing)}")
    print(f"\nOutput file: {output_file}")
    print("\n" + "=" * 80)
    print("PRODUCTS WITH PRICING:")
    print("=" * 80)
    
    for i, product in enumerate(products_with_pricing, 1):
        print(f"\n{i}. {product['Product Name']}")
        print(f"   Manufacturer: {product['Manufacturer']}")
        print(f"   Price: {product['Estimated Wholesale Price']}")
        print(f"   Match: {product['Match Score']}")
        print(f"   URL: {product['Solicitation URL']}")
    
    return output_file

if __name__ == "__main__":
    create_pricing_summary()
