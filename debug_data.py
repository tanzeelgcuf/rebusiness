import sqlite3
import json

DB_PATH = "rebusiness_automation.db"

def inspect_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Pick one of the contract IDs from preview_email.py
    contract_id = '04f3e1a2905844b994298c793f3ff78e' 
    
    cursor.execute("SELECT analysis_summary, data FROM solicitations WHERE contract_id = ?", (contract_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        analysis_json = row[0]
        data_json = row[1]
        
        print(f"--- Analysis JSON for {contract_id} ---")
        if analysis_json:
            try:
                parsed = json.loads(analysis_json)
                print(json.dumps(parsed, indent=2))
            except:
                print("RAW (Not JSON):", analysis_json)
        else:
            print("None")

        print(f"\n--- Data JSON for {contract_id} ---")
        if data_json:
             try:
                parsed = json.loads(data_json)
                print(json.dumps(parsed, indent=2))
             except:
                print("RAW (Not JSON):", data_json)
    else:
        print("Contract not found")

if __name__ == "__main__":
    inspect_data()
