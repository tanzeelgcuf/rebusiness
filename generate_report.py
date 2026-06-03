import sqlite3
import json
import pandas as pd
from database_manager import DatabaseManager

def generate_report():
    db_path = "rebusiness_automation.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=== Outreach Status Report ===\n")

    # 1. Thomasnet Wholesalers Sourcing Status
    print("--- 1. Thomasnet Sourcing ---")
    try:
        cursor.execute("SELECT COUNT(*) FROM vendors WHERE past_performance_summary LIKE '%ThomasNet%'")
        thomasnet_count = cursor.fetchone()[0]
        print(f"Total Vendors Sourced via ThomasNet: {thomasnet_count}")
    except Exception as e:
        print(f"Error querying Thomasnet vendors: {e}")

    # 2. Products with Exact Information
    print("\n--- 2. Product Extraction ---")
    try:
        # Check 'products' table first
        cursor.execute("SELECT COUNT(*) FROM products")
        products_table_count = cursor.fetchone()[0]
        
        # Check solicitations table for JSON data if products table is empty
        cursor.execute("SELECT data FROM solicitations WHERE data IS NOT NULL")
        solicitations_data = cursor.fetchall()
        
        extracted_products_count = 0
        exact_info_count = 0
        
        for row in solicitations_data:
            try:
                data = json.loads(row[0])
                if 'products' in data and isinstance(data['products'], list):
                    for p in data['products']:
                        extracted_products_count += 1
                        # Check for 'exact information' (e.g., quantity and specs)
                        if p.get('quantity') and p.get('specifications') or p.get('description'):
                            exact_info_count += 1
            except:
                pass

        print(f"Products in 'products' table: {products_table_count}")
        print(f"Total Products Extracted (from JSON): {extracted_products_count}")
        print(f"Products with Exact Info (Qty + Specs/Desc): {exact_info_count}")

    except Exception as e:
        print(f"Error querying products: {e}")

    # 3 & 4. Outreach Progress (Emails vs Forms)
    print("\n--- 3. Outreach Progress ---")
    try:
        # Check vendors email_status
        cursor.execute("SELECT email_status, COUNT(*) FROM vendors GROUP BY email_status")
        status_counts = cursor.fetchall()
        
        print("Vendor Status Breakdown:")
        for status, count in status_counts:
            print(f"  - {status}: {count}")
            
        # Specific check for bobbysmitty078@gmail.com (Assuming this is the sender email, 
        # but usually we track 'Sent' status. If the user wants to know HOW MANY from that email,
        # we might assume all 'Sent' emails are from the configured sender.)
        
        # Check if there is a 'method' column or similar in vendors? No.
        # But 'email_status' often reflects the result.
        
        # Also check manufacturer_requests if populated
        # cursor.execute("SELECT COUNT(*) FROM manufacturer_requests")
        # req_count = cursor.fetchone()[0]
        # print(f"Entries in manufacturer_requests table: {req_count}")

    except Exception as e:
        print(f"Error querying outreach status: {e}")
        
    print("\n==============================")
    conn.close()

if __name__ == "__main__":
    generate_report()
