#!/usr/bin/env python3
import sqlite3
import json

DB_PATH = "rebusiness_automation.db"
target_ids = ["796b8188161049bfa359c2b16432e946", "04f3e1a2905844b994298c793f3ff78e", "d4c90fd103a2402a88d306a6c4dce262", "cc36deeb238c4481888bee066b255901", "a1edf238787e4f4a83a87997bff9087e", "8e3c806a4472495fb936e1e2493f3304", "e6fc48127e6041e5943291cf31192b7c", "197aaa46ad6c461db627c6934ba7fea4"]

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for cid in target_ids:
        cursor.execute("SELECT sa.analysis_json, s.title FROM solicitation_analysis sa JOIN solicitations s ON sa.contract_id = s.contract_id WHERE sa.contract_id = ?", (cid,))
        row = cursor.fetchone()
        if not row:
            print(f"ID {cid} not found in analysis.")
            continue
        
        data = json.loads(row[0])
        print(f"\n--- Analysis for {cid} ({row[1][:40]}) ---")
        print(f"Entity: {data.get('soliciting_entity')}")
        print(f"Due Date: {data.get('quotes_due_date')}")
        print(f"Set-Aside: {data.get('set_aside_type')}")
        
        # Check rich sections
        print(f"Insurance Req: {bool(data.get('insurance_requirements'))}")
        print(f"Wage Req: {bool(data.get('wage_labor_requirements'))}")
        print(f"Security Req: {bool(data.get('security_compliance'))}")
        print(f"Checklist: {len(data.get('submission_checklist', []))} items")
        print(f"CLINs: {len(data.get('clins', []))} items")
        
        fallbacks = row[0].count("Information not provided") + row[0].count("NOT_FOUND") + row[0].count("N/A")
        print(f"Fallbacks: {fallbacks}")

    conn.close()

if __name__ == "__main__":
    main()
