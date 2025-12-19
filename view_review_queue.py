from database_manager import DatabaseManager
import pandas as pd

def view_queue():
    db = DatabaseManager()
    conn = db._connect_db()
    
    # Fetch Flagged
    query = "SELECT contract_id, title, extraction_confidence, review_status FROM solicitations WHERE review_status='flagged'"
    df = pd.read_sql_query(query, conn)
    db._close_db()
    
    print("\n" + "="*60)
    print("🚩 MANUAL REVIEW QUEUE")
    print("="*60)
    
    if df.empty:
        print("No items flagged for review. All systems nominal.")
    else:
        print(f"Found {len(df)} flagged item(s):\n")
        # Adjust display options
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        pd.set_option('display.max_colwidth', 50)
        
        print(df.to_string(index=False))
        
    print("="*60 + "\n")

if __name__ == "__main__":
    view_queue()
