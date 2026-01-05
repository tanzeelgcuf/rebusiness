#!/usr/bin/env python3
import sqlite3
import json

DB_PATH = "rebusiness_automation.db"
target_ids = ["796b8188161049bfa359c2b16432e946", "04f3e1a2905844b994298c793f3ff78e", "d4c90fd103a2402a88d306a6c4dce262", "cc36deeb238c4481888bee066b255901", "a1edf238787e4f4a83a87997bff9087e", "8e3c806a4472495fb936e1e2493f3304", "e6fc48127e6041e5943291cf31192b7c", "197aaa46ad6c461db627c6934ba7fea4"]

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for cid in target_ids:
        cursor.execute("SELECT analysis_summary, title FROM solicitations WHERE contract_id = ?", (cid,))
        row = cursor.fetchone()
        if not row or not row[0]:
            print(f"\nID {cid}: NOT FOUND OR NO SUMMARY")
            continue
        
        try:
            data = json.loads(row[0])
            print(f"\n--- {cid[:10]} | {row[1][:30]} ---")
            print(f"  Entity: {data.get('soliciting_entity') or 'MISSING'}")
            print(f"  Due Date: {data.get('quotes_due_date') or 'MISSING'}")
            print(f"  Set-Aside: {data.get('set_aside_type') or 'MISSING'}")
            print(f"  Category: {data.get('solicitation_category') or 'MISSING'}")
            
            # Count sections
            ins = bool(data.get('insurance_requirements'))
            wage = bool(data.get('wage_labor_requirements'))
            sec = bool(data.get('security_compliance'))
            check = len(data.get('submission_checklist', []))
            clins = len(data.get('clins', []))
            prods = len(data.get('product_details', []))
            
            print(f"  Sections: Insurance:{ins}, Wage:{wage}, Security:{sec}, Checklist:{check}, CLINs:{clins}, Prods:{prods}")
            
            # Check for generic fallbacks
            fallbacks = row[0].count("Information not provided") + row[0].count("NOT_FOUND")
            print(f"  Fallbacks: {fallbacks}")
        except Exception as e:
            print(f"\n--- {cid[:10]} | ERROR: {e}")

    conn.close()

if __name__ == "__main__":
    main()
