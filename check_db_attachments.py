import sqlite3
import os

DB_PATH = "rebusiness_automation.db"

def check_attachments(contract_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM attachments WHERE contract_id = ?", (contract_id,))
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} attachments for {contract_id}.")
    for row in rows:
        print(f"File: {row['file_name']} (Path: {row['file_path']})")
    
    conn.close()

if __name__ == "__main__":
    check_attachments("89d87524e3")
