import os
import sys
import glob
import sqlite3
from datetime import datetime
from pathlib import Path

# Add parent directory to path
current_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(current_dir))

from database_manager import DatabaseManager
from dashboard.utils.dashboard_thomasnet import extract_product_name

def sync_database():
    """Sync existing RFQ files into the database"""
    print("Starting database sync...")
    db = DatabaseManager()
    
    # improved pattern to find all rfq docx files recursively
    base_dir = os.path.join(current_dir, "rfq_downloads")
    pattern = os.path.join(base_dir, "**", "*_RFQ_PRODUCT.docx")
    rfq_files = glob.glob(pattern, recursive=True)
    
    print(f"Found {len(rfq_files)} RFQ files on disk")
    
    conn = db._connect_db()
    cursor = conn.cursor()
    
    count_added = 0
    count_skipped = 0
    
    for file_path in rfq_files:
        try:
            filename = os.path.basename(file_path)
            # Filename format: {contract_id}_RFQ_PRODUCT.docx
            if "_RFQ_PRODUCT.docx" not in filename:
                continue
                
            contract_id = filename.replace("_RFQ_PRODUCT.docx", "")
            
            # Check if exists in RFQ table
            cursor.execute("SELECT 1 FROM rfq_outputs WHERE contract_id = ?", (contract_id,))
            if cursor.fetchone():
                count_skipped += 1
                continue
                
            # Get creation time
            created_timestamp = os.path.getctime(file_path)
            created_date = datetime.fromtimestamp(created_timestamp).isoformat()
            
            # Extract info
            product_name = extract_product_name(file_path)
            
            # Ensure solicitation exists
            cursor.execute("SELECT 1 FROM solicitations WHERE contract_id = ?", (contract_id,))
            if not cursor.fetchone():
                # Insert dummy solicitation if missing
                print(f"Adding missing solicitation: {contract_id}")
                cursor.execute("""
                    INSERT INTO solicitations (contract_id, title, url, description, posted_date, due_date, active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (
                    contract_id, 
                    f"Solicitation for {product_name}", 
                    f"https://sam.gov/opp/{contract_id}/view",
                    f"Automatically synced solicitation for {product_name}",
                    created_date,
                    created_date
                ))
            
            # Insert RFQ
            print(f"Adding RFQ: {contract_id}")
            cursor.execute("""
                INSERT INTO rfq_outputs (contract_id, rfq_query, rfq_content, generated_date, file_path)
                VALUES (?, ?, ?, ?, ?)
            """, (
                contract_id,
                product_name,
                "Content not indexed", # We could read the file but it's binary/docx
                created_date,
                file_path
            ))
            
            count_added += 1
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\nSync complete!")
    print(f"Added: {count_added}")
    print(f"Skipped: {count_skipped}")
    print(f"Total: {len(rfq_files)}")

if __name__ == "__main__":
    # Mock extract_solicitation_title if strictly needed or rely on fallback
    sync_database()
