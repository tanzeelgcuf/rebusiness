
import sqlite3
import os

def check_db():
    db_path = 'rebusiness_automation.db'
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check for notice_id
    nid = "N00104-25-Q-NF13"
    cursor.execute("SELECT * FROM solicitations WHERE contract_id = ?", (nid,)) # Note: contract_id is the column name in schema
    row = cursor.fetchone()
    
    if row:
        print(f"Found solicitation: {row}")
        # Get columns
        cols = [description[0] for description in cursor.description]
        row_dict = dict(zip(cols, row))
        print("Details:", row_dict)
    else:
        print(f"Notice ID {nid} not found in database.")
        
        # Try partial match
        cursor.execute("SELECT contract_id FROM solicitations WHERE contract_id LIKE ?", ('%N00104%',))
        rows = cursor.fetchall()
        print("Similar IDs:", [r[0] for r in rows])

    conn.close()

if __name__ == "__main__":
    check_db()
