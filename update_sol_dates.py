import sqlite3
import json

DB_PATH = "rebusiness_automation.db"

DATES_MAP = {
    '04f3e1a2905844b994298c793f3ff78e': {'pub': 'Dec 20, 2025', 'due': 'Jan 20, 2026'},
    '197aaa46ad6c461db627c6934ba7fea4': {'pub': 'Dec 19, 2025', 'due': 'Dec 26, 2025'},
    '796b8188161049bfa359c2b16432e946': {'pub': 'Dec 19, 2025', 'due': 'Dec 31, 2026'},
    'cc36deeb238c4481888bee066b255901': {'pub': 'Dec 19, 2025', 'due': 'Dec 29, 2025'},
    'a1edf238787e4f4a83a87997bff9087e': {'pub': 'Dec 20, 2025', 'due': 'Information not provided in solicitation'},
    '8e3c806a4472495fb936e1e2493f3304': {'pub': 'Dec 19, 2025', 'due': 'Dec 29, 2025'},
    'd4c90fd103a2402a88d306a6c4dce262': {'pub': 'Dec 19, 2025', 'due': 'Dec 26, 2025'},
    'e6fc48127e6041e5943291cf31192b7c': {'pub': 'Dec 20, 2025', 'due': 'Dec 29, 2025'}
}

def update_dates():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for cid, dates in DATES_MAP.items():
        cursor.execute("SELECT analysis_summary FROM solicitations WHERE contract_id = ?", (cid,))
        row = cursor.fetchone()
        if not row:
            print(f"Skipping {cid} - Not found.")
            continue
            
        try:
            summary = json.loads(row[0])
            summary['solicitation_date'] = dates['pub']
            summary['quotes_due_date'] = dates['due']
            
            # Also update clins if necessary (optional)
            
            new_json = json.dumps(summary)
            cursor.execute("UPDATE solicitations SET analysis_summary = ? WHERE contract_id = ?", (new_json, cid))
            print(f"Updated {cid}")
        except Exception as e:
            print(f"Error updating {cid}: {e}")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_dates()
