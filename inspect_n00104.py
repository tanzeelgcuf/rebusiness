
import sqlite3
import os

def inspect_n00104_source():
    db_path = 'rebusiness_automation.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    nid = "N0010425QNF13"
    print(f"--- Solicitation Details for {nid} ---")
    cursor.execute("SELECT * FROM solicitations WHERE contract_id = ?", (nid,))
    row = cursor.fetchone()
    if row:
        print(f"URL: {row['url']}")
        print(f"Title: {row['title']}")
        print(f"Date Created: {row['created_at']}")
    else:
        print("Solicitation not found.")
        return

    print("\n--- Attachments ---")
    cursor.execute("SELECT * FROM attachments WHERE contract_id = ?", (nid,))
    atts = cursor.fetchall()
    if atts:
        for a in atts:
            exists = "EXISTS" if os.path.exists(a['file_path']) else "MISSING"
            print(f"File: {a['file_name']}")
            print(f"Path: {a['file_path']} [{exists}]")
    else:
        print("No attachments found in DB.")

    conn.close()

if __name__ == "__main__":
    inspect_n00104_source()
