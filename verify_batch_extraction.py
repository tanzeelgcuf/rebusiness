#!/usr/bin/env python3
import sqlite3
import json

DB_PATH = "rebusiness_automation.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT sa.contract_id, s.title, sa.analysis_json, (SELECT COUNT(*) FROM attachments a WHERE a.contract_id = sa.contract_id) as att_count
        FROM solicitation_analysis sa
        JOIN solicitations s ON sa.contract_id = s.contract_id
    """)
    rows = cursor.fetchall()
    
    print(f"{'Contract ID':<15} {'Att':<5} {'Entity':<20} {'Due Date':<15} {'Set-Aside':<15} {'Fallbacks'}")
    print("-" * 100)
    
    for cid, title, a_json, att_count in rows:
        try:
            data = json.loads(a_json)
            entity = data.get('soliciting_entity') or "MISSING"
            due = data.get('quotes_due_date') or "MISSING"
            set_aside = data.get('set_aside_type') or "MISSING"
            
            # Count "Information not provided" or "MISSING" in a sample email generation
            fallbacks = a_json.count("Information not provided") + a_json.count("NOT_FOUND") + a_json.count("N/A")
            
            print(f"{cid[:15]:<15} {att_count:<5} {str(entity)[:20]:<20} {str(due)[:15]:<15} {str(set_aside)[:15]:<15} {fallbacks}")
        except:
             print(f"{cid[:15]:<15} {att_count:<5} ERROR PARSING JSON")
             
    conn.close()

if __name__ == "__main__":
    main()
