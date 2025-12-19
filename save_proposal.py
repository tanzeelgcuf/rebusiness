import sqlite3
import json
import os

DATABASE_NAME = "rebusiness_automation.db"

def save_product_proposal_as_markdown():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    cursor = conn.cursor()

    # Find a product-based solicitation
    cursor.execute("SELECT contract_id, title FROM solicitations WHERE product_requirements IS NOT NULL LIMIT 1")
    solicitation = cursor.fetchone()

    if not solicitation:
        print("No product-based solicitations found in the database.")
        conn.close()
        return

    contract_id = solicitation['contract_id']
    title = solicitation['title']

    # Retrieve the proposal text
    cursor.execute("SELECT proposal_text FROM proposals WHERE contract_id = ?", (contract_id,))
    proposal = cursor.fetchone()

    if not proposal:
        print(f"No proposal found for contract ID: {contract_id}.")
        conn.close()
        return

    proposal_text = proposal['proposal_text']
    
    # Create a clean filename
    filename = f"proposal_{contract_id}.md"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(proposal_text)
    
    print(f"Successfully saved proposal for '{title}' (Contract ID: {contract_id}) to {filename}")

    conn.close()

if __name__ == "__main__":
    save_product_proposal_as_markdown()
