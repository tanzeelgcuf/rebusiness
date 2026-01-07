import sqlite3
import os

DB_PATH = "rebusiness_automation.db"

def check_analysis(contract_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT analysis_summary, description FROM solicitations WHERE contract_id = ?", (contract_id,))
    row = cursor.fetchone()
    
    if row:
        summary = row['analysis_summary']
        description = row['description']
        print(f"Analysis Summary present: {bool(summary)}")
        if summary:
            print(f"Analysis Summary length: {len(summary)}")
        print(f"Description length: {len(description) if description else 0}")
    else:
        print("Solicitation not found.")
    
    conn.close()

if __name__ == "__main__":
    check_analysis("89d87524e3")
