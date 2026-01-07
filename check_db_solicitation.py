import sqlite3
import os

DB_PATH = "rebusiness_automation.db"

def check_solicitation(partial_id):
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print(f"Searching for contract_id like '%{partial_id}%'...")
    cursor.execute("SELECT * FROM solicitations WHERE contract_id LIKE ?", (f"%{partial_id}%",))
    rows = cursor.fetchall()
    
    if rows:
        print(f"Found {len(rows)} matching solicitations:")
        for row in rows:
            print(f"Contract ID: {row['contract_id']}")
            print(f"URL: {row['url']}")
            print(f"Title: {row['title']}")
            print("-" * 20)
    else:
        print("No matching solicitation found.")
    
    conn.close()

if __name__ == "__main__":
    check_solicitation("89d87524e3")
