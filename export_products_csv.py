#!/usr/bin/env python3
"""
Export Products to CSV
Exports all products from the database to a CSV file with solicitation links.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database_manager import DatabaseManager
import csv
from datetime import datetime

def export_products_to_csv():
    """Export all products to CSV with solicitation information."""
    
    db = DatabaseManager()
    
    # Get all products with solicitation info
    conn = db._connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            p.id,
            p.product_name,
            p.description,
            p.specifications,
            p.quantity,
            p.naics_code,
            p.contract_id,
            s.title as solicitation_title,
            s.url as solicitation_url,
            s.location,
            p.created_at
        FROM products p
        LEFT JOIN solicitations s ON p.contract_id = s.contract_id
        ORDER BY p.created_at DESC
    """)
    products = cursor.fetchall()
    db._close_db()
    
    # Create CSV filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"products_export_{timestamp}.csv"
    csv_path = os.path.join(os.path.dirname(__file__), csv_filename)
    
    # Write to CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'Product ID',
            'Product Name',
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
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for product in products:
            # Truncate description if too long
            description = product['description']
            if description and len(description) > 200:
                description = description[:197] + "..."
            
            writer.writerow({
                'Product ID': product['id'],
                'Product Name': product['product_name'],
                'Description': description or '',
                'Specifications': product['specifications'] or '',
                'Quantity': product['quantity'] or '',
                'NAICS Code': product['naics_code'] or '',
                'Contract ID': product['contract_id'],
                'Solicitation Title': product['solicitation_title'] or '',
                'Solicitation URL': product['solicitation_url'] or '',
                'Location': product['location'] or '',
                'Date Added': product['created_at']
            })
    
    print(f"✅ Exported {len(products)} products to: {csv_path}")
    print(f"\nCSV file location: {csv_path}")
    
    return csv_path

if __name__ == "__main__":
    export_products_to_csv()
