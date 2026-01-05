
import sqlite3
import json
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from reanalyze_solicitations import reanalyze_solicitation

def reanalyze_specific_contract(contract_id):
    conn = sqlite3.connect("rebusiness_automation.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, url, data, (SELECT COUNT(*) FROM attachments WHERE contract_id = ?) FROM solicitations WHERE contract_id = ?", (contract_id, contract_id))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        title, url, old_data, att_count = row
        print(f"Forcing re-analysis for {contract_id} with {att_count} attachments...")
        reanalyze_solicitation(contract_id, title, url, old_data, att_count)
    else:
        print(f"Contract {contract_id} not found")

if __name__ == "__main__":
    reanalyze_specific_contract("197aaa46ad6c461db627c6934ba7fea4")
