import sqlite3
import json
import os
import sys

# Add local path to import functions
from run_email_campaign import format_service_email_body, format_product_email_body

def verify_real_data():
    conn = sqlite3.connect("rebusiness_automation.db")
    cursor = conn.cursor()

    test_cases = [
        {"cid": "22c422c6b9", "type": "Product", "desc": "Medical Product (BACT/ALERT)"},
        {"cid": "d497288c4a", "type": "Service", "desc": "Service (Engineering Technician Support)"},
        {"cid": "020addf92a20484485353181a4f6b5bf", "type": "Product", "desc": "Medical Product (Ventilators)"}
    ]

    for case in test_cases:
        print(f"\n{'='*20} {case['desc']} {'='*20}")
        cid = case["cid"]
        
        # Get Solicitation Data
        cursor.execute("SELECT title, analysis_summary, data, url FROM solicitations WHERE contract_id = ?", (cid,))
        sol_row = cursor.fetchone()
        if not sol_row:
            print(f"Error: Solicitation {cid} not found.")
            continue
            
        sol_title, analysis_json, sol_data_json, sol_url = sol_row
        
        # Get first product associated with this contract
        cursor.execute("SELECT product_name, quantity, specifications FROM products WHERE contract_id = ? LIMIT 1", (cid,))
        product_row = cursor.fetchone()
        
        product_name = product_row[0] if product_row else "Unknown Product"
        quantity = product_row[1] if product_row else "Unknown Qty"
        specs = product_row[2] if product_row else "No Specs"
        
        due_date = "2026-01-30" # Default future date for testing
        if sol_data_json:
            try:
                sdata = json.loads(sol_data_json)
                due_date = sdata.get('due_date') or sdata.get('Due Date') or due_date
            except: pass

        if case["type"] == "Product":
            subject, body, html = format_product_email_body(cid, sol_title, product_name, quantity, specs, "{}", None, None, due_date, sol_url, analysis_json)
        else:
            subject, body, html = format_service_email_body(cid, sol_title, product_name, quantity, specs, "{}", None, None, due_date, sol_url, analysis_json)
            
        print(f"SUBJECT: {subject}")
        print("-" * 20)
        print(body)
        print("\n")

    conn.close()

if __name__ == "__main__":
    verify_real_data()
