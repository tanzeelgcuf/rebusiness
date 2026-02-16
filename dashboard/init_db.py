#!/usr/bin/env python3
"""
Initialize database with ThomasNet submissions table
"""

import sys
sys.path.append('..')

from database_manager import DatabaseManager

def init_thomasnet_table():
    """Add ThomasNet submissions table to existing database"""
    try:
        db = DatabaseManager()
        conn = db._connect_db()
        cursor = conn.cursor()
        
        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thomasnet_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT,
                rfq_file_path TEXT,
                vendor_name TEXT,
                vendor_company TEXT,
                vendor_location TEXT,
                product_searched TEXT,
                submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT 1,
                error_message TEXT,
                FOREIGN KEY (contract_id) REFERENCES solicitations(contract_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thomasnet_contract ON thomasnet_submissions(contract_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thomasnet_timestamp ON thomasnet_submissions(submission_timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thomasnet_vendor ON thomasnet_submissions(vendor_company)")
        
        conn.commit()
        db._close_db()
        
        print("✅ ThomasNet submissions table created successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False

if __name__ == "__main__":
    init_thomasnet_table()
