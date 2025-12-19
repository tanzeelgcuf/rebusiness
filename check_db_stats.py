import sqlite3
import os
from database_manager import DatabaseManager

def check_stats():
    db = DatabaseManager()
    conn = db._connect_db()
    cursor = conn.cursor()
    
    print("\n=== Database Statistics ===")
    
    # 1. Solicitations Count
    sol_count = cursor.execute("SELECT COUNT(*) FROM solicitations").fetchone()[0]
    print(f"Total Solicitations: {sol_count}")
    
    # 2. Solicitations with Analysis
    analyzed_count = cursor.execute("SELECT COUNT(*) FROM solicitations WHERE analysis_summary IS NOT NULL").fetchone()[0]
    print(f"Analyzed Solicitations: {analyzed_count}")
    
    # 3. Products Count
    prod_count = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    print(f"Total Extracted Products: {prod_count}")
    
    # 4. Sourcing Status
    print("\n--- Product Sourcing Status ---")
    status_counts = cursor.execute("""
        SELECT 
            COALESCE(s.status, 'pending') as status, 
            COUNT(*) as count
        FROM products p
        LEFT JOIN product_sourcing_status s ON p.id = s.product_id
        GROUP BY status
    """).fetchall()
    
    if not status_counts:
        print("No sourcing records found (All 'pending').")
    else:
        for status, count in status_counts:
            print(f"  {status}: {count}")

    # 5. Suppliers Found
    supplier_count = cursor.execute("SELECT COUNT(*) FROM product_suppliers").fetchone()[0]
    print(f"\nTotal Suppliers Found: {supplier_count}")
    
    # 6. Sample Products (if any)
    if prod_count > 0:
        print("\n--- Sample Products (First 5) ---")
        rows = cursor.execute("SELECT product_name, quantity FROM products LIMIT 5").fetchall()
        for r in rows:
            print(f"  - {r['product_name']} (Qty: {r['quantity']})")

    conn.close()

if __name__ == "__main__":
    check_stats()
