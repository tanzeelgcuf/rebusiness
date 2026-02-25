#!/usr/bin/env python3
"""Add dashboard methods to DatabaseManager class"""

# Read the current file
with open('database_manager.py', 'r') as f:
    content = f.read()

# Dashboard methods to add
dashboard_methods = '''
    # ========================================================================
    # Dashboard API Methods
    # ========================================================================
    
    def get_all_rfqs(self, limit=50, offset=0):
        """Get RFQs with pagination for dashboard"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT r.*, s.title as solicitation_title
                FROM rfq_outputs r
                LEFT JOIN solicitations s ON r.contract_id = s.contract_id
                ORDER BY r.generated_date DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            rfqs = [dict(row) for row in cursor.fetchall()]
            return rfqs
        finally:
            self._close_db()

    def get_rfqs_count(self):
        """Get total RFQ count"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM rfq_outputs")
            count = cursor.fetchone()[0]
            return count
        finally:
            self._close_db()

    def get_rfq_by_contract(self, contract_id):
        """Get RFQ by contract ID"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT r.*, s.title as solicitation_title, s.description
                FROM rfq_outputs r
                LEFT JOIN solicitations s ON r.contract_id = s.contract_id
                WHERE r.contract_id = ?
            """, (contract_id,))
            rfq = cursor.fetchone()
            return dict(rfq) if rfq else None
        finally:
            self._close_db()

    def get_vendor_submissions(self, limit=100, offset=0):
        """Get vendor submissions with pagination"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM vendors
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            vendors = [dict(row) for row in cursor.fetchall()]
            return vendors
        finally:
            self._close_db()

    def get_vendor_submissions_count(self):
        """Get total vendor count"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM vendors")
            count = cursor.fetchone()[0]
            return count
        finally:
            self._close_db()

    def get_vendor_stats(self):
        """Get vendor statistics"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT name) as unique_vendors,
                    SUM(CASE WHEN email_status = 'Sent' THEN 1 ELSE 0 END) as contacted
                FROM vendors
            """)
            row = cursor.fetchone()
            stats = dict(row) if row else {'total': 0, 'unique_vendors': 0, 'contacted': 0}
            return stats
        finally:
            self._close_db()

    def get_solicitation_stats(self):
        """Get solicitation statistics"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN created_at >= datetime('now', '-7 days') THEN 1 END) as this_week
                FROM solicitations
            """)
            row = cursor.fetchone()
            stats = dict(row) if row else {'total': 0, 'this_week': 0}
            return stats
        finally:
            self._close_db()

    def get_vendors_by_product(self):
        """Get vendors grouped by product"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT contract_id, COUNT(*) as vendor_count
                FROM vendors
                GROUP BY contract_id
                ORDER BY vendor_count DESC
            """)
            results = [dict(row) for row in cursor.fetchall()]
            return results
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
            
            # Vendor submissions
            cursor.execute("SELECT COUNT(*) FROM vendors")
            stats['successful_submissions'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT name) FROM vendors")
            stats['unique_vendors'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM vendors 
                WHERE created_at >= datetime('now', '-7 days')
            """)
            stats['submissions_last_week'] = cursor.fetchone()[0]
            
            return stats
        finally:
            self._close_db()
'''

# Append before the final newline
if content.endswith('\n'):
    content = content[:-1] + dashboard_methods + '\n'
else:
    content = content + dashboard_methods

# Write back
with open('database_manager.py', 'w') as f:
    f.write(content)

print("✅ Dashboard methods added successfully!")
print(f"File now has {len(content.splitlines())} lines")
