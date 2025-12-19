from database_manager import DatabaseManager
import pandas as pd

def view_products():
    db = DatabaseManager()
    conn = db._connect_db()
    
    # Fetch Products with related Solicitation Title
    query = """
        SELECT 
            p.contract_id,
            s.title as solicitation_title,
            p.product_name,
            p.quantity,
            p.specifications
        FROM products p
        LEFT JOIN solicitations s ON p.contract_id = s.contract_id
        ORDER BY p.created_at DESC
        LIMIT 20
    """
    df = pd.read_sql_query(query, conn)
    db._close_db()
    
    print("\n" + "="*80)
    print("📦 EXTRACTED PRODUCTS (LATEST 20)")
    print("="*80)
    
    if df.empty:
        print("No products extracted yet.")
    else:
        # Display each item in a readable block format
        for index, row in df.iterrows():
            print(f"[{index+1}] {row['solicitation_title']} ({row['contract_id']})")
            print(f"    Product:  {row['product_name']}")
            print(f"    Quantity: {row['quantity']}")
            print(f"    Specs:    {row['specifications']}")
            print("-" * 80)

    print("\n")

if __name__ == "__main__":
    view_products()
