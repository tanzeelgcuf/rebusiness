
import sqlite3

DATABASE_NAME = "rebusiness_automation.db"

def check_counts():
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Check Solicitations
        cursor.execute("SELECT COUNT(*) FROM solicitations")
        solicitation_count = cursor.fetchone()[0]
        
        # Check Products
        # First check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM products")
            product_count = cursor.fetchone()[0]
        else:
            product_count = "Table 'products' does not exist"

        print(f"Solicitation Count: {solicitation_count}")
        print(f"Product Count: {product_count}")

        # Check Manufacturers
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='manufacturers'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM manufacturers")
            manufacturer_count = cursor.fetchone()[0]
        else:
            manufacturer_count = "Table 'manufacturers' does not exist"
        
        print(f"Manufacturer Count: {manufacturer_count}")
        
        conn.close()
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    check_counts()
