"""
Dashboard Extensions for DatabaseManager
Add these methods to the DatabaseManager class for dashboard functionality
"""

# Add to DatabaseManager class:

def add_thomasnet_submission(self, contract_id, vendor_name, vendor_company, 
                            vendor_location, product_searched, rfq_file_path,
                            success=True, error_message=None):
    """Records a ThomasNet vendor submission"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO thomasnet_submissions 
            (contract_id, vendor_name, vendor_company, vendor_location, 
             product_searched, rfq_file_path, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (contract_id, vendor_name, vendor_company, vendor_location,
              product_searched, rfq_file_path, success, error_message))
        conn.commit()
        print(f"Logged ThomasNet submission: {vendor_company} for {contract_id}")
        return True
    except Exception as e:
        print(f"Error logging ThomasNet submission: {e}")
        conn.rollback()
        return False
    finally:
        self._close_db()

def get_all_solicitations(self, limit=50, offset=0, search=''):
    """Get solicitations with pagination and search"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        if search:
            cursor.execute("""
                SELECT * FROM solicitations 
                WHERE title LIKE ? OR contract_id LIKE ? OR description LIKE ?
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            """, (f'%{search}%', f'%{search}%', f'%{search}%', limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM solicitations 
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            """, (limit, offset))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        self._close_db()

def get_solicitations_count(self, search=''):
    """Get total count of solicitations"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        if search:
            cursor.execute("""
                SELECT COUNT(*) FROM solicitations 
                WHERE title LIKE ? OR contract_id LIKE ? OR description LIKE ?
            """, (f'%{search}%', f'%{search}%', f'%{search}%'))
        else:
            cursor.execute("SELECT COUNT(*) FROM solicitations")
        
        count = cursor.fetchone()[0]
        return count
    finally:
        self._close_db()

def get_solicitation_by_id(self, contract_id):
    """Get solicitation by contract_id"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM solicitations WHERE contract_id = ?", (contract_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        self._close_db()

def get_all_rfqs(self, limit=50, offset=0):
    """Get all RFQs with pagination"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT r.*, s.title as solicitation_title, s.created_at as solicitation_date
            FROM rfq_outputs r
            LEFT JOIN solicitations s ON r.contract_id = s.contract_id
            ORDER BY r.generated_date DESC LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        self._close_db()

def get_rfqs_count(self):
    """Get total count of RFQs"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM rfq_outputs")
        count = cursor.fetchone()[0]
        return count
    finally:
        self._close_db()

def get_rfq_by_contract(self, contract_id):
    """Get RFQ by contract_id"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT r.*, s.title as solicitation_title, s.description
            FROM rfq_outputs r
            LEFT JOIN solicitations s ON r.contract_id = s.contract_id
            WHERE r.contract_id = ?
        """, (contract_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        self._close_db()

def update_rfq_content(self, contract_id, content):
    """Update RFQ content"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE rfq_outputs 
            SET rfq_content = ?, generated_date = CURRENT_TIMESTAMP
            WHERE contract_id = ?
        """, (content, contract_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating RFQ content: {e}")
        conn.rollback()
        return False
    finally:
        self._close_db()

def get_vendor_submissions(self, limit=100, offset=0):
    """Get all ThomasNet vendor submissions"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT t.*, s.title as solicitation_title
            FROM thomasnet_submissions t
            LEFT JOIN solicitations s ON t.contract_id = s.contract_id
            ORDER BY t.submission_timestamp DESC LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        self._close_db()

def get_vendor_submissions_count(self):
    """Get total count of vendor submissions"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM thomasnet_submissions")
        count = cursor.fetchone()[0]
        return count
    finally:
        self._close_db()

def get_vendor_stats(self):
    """Get vendor statistics"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        stats = {}
        
        # Total submissions
        cursor.execute("SELECT COUNT(*) FROM thomasnet_submissions")
        stats['total_submissions'] = cursor.fetchone()[0]
        
        # Successful submissions
        cursor.execute("SELECT COUNT(*) FROM thomasnet_submissions WHERE success = 1")
        stats['successful_submissions'] = cursor.fetchone()[0]
        
        # Unique vendors
        cursor.execute("SELECT COUNT(DISTINCT vendor_company) FROM thomasnet_submissions")
        stats['unique_vendors'] = cursor.fetchone()[0]
        
        # Recent submissions (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) FROM thomasnet_submissions 
            WHERE submission_timestamp >= datetime('now', '-7 days')
        """)
        stats['submissions_last_week'] = cursor.fetchone()[0]
        
        return stats
    finally:
        self._close_db()

def get_vendors_by_product(self):
    """Get vendors grouped by product"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT product_searched, COUNT(*) as vendor_count,
                   GROUP_CONCAT(vendor_company, ', ') as vendors
            FROM thomasnet_submissions
            GROUP BY product_searched
            ORDER BY vendor_count DESC
        """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        self._close_db()

def get_dashboard_stats(self):
    """Get overall dashboard statistics"""
    conn = self._connect_db()
    cursor = conn.cursor()
    try:
        stats = {}
        
        # Solicitations
        cursor.execute("SELECT COUNT(*) FROM solicitations")
        stats['total_solicitations'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM solicitations 
            WHERE created_at >= datetime('now', '-7 days')
        """)
        stats['solicitations_last_week'] = cursor.fetchone()[0]
        
        # RFQs
        cursor.execute("SELECT COUNT(*) FROM rfq_outputs")
        stats['total_rfqs'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM rfq_outputs 
            WHERE generated_date >= datetime('now', '-7 days')
        """)
        stats['rfqs_last_week'] = cursor.fetchone()[0]
        
        # ThomasNet submissions
        cursor.execute("SELECT COUNT(*) FROM thomasnet_submissions WHERE success = 1")
        stats['successful_submissions'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT vendor_company) FROM thomasnet_submissions")
        stats['unique_vendors'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM thomasnet_submissions 
            WHERE submission_timestamp >= datetime('now', '-7 days')
        """)
        stats['submissions_last_week'] = cursor.fetchone()[0]
        
        return stats
    finally:
        self._close_db()

# Add this to create_tables() method (in the cursor.execute() section after rfq_outputs):

def _add_thomasnet_table(self):
    """Add ThomasNet submissions table (call from create_tables)"""
    conn = self._connect_db()
    cursor = conn.cursor()
    
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
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thomasnet_contract ON thomasnet_submissions(contract_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thomasnet_timestamp ON thomasnet_submissions(submission_timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thomasnet_vendor ON thomasnet_submissions(vendor_company)")
    except:
        pass
    
    conn.commit()
    self._close_db()
