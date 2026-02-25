#!/usr/bin/env python3
"""Add solicitation methods with pagination to DatabaseManager class"""

# Read the current file
with open('database_manager.py', 'r') as f:
    content = f.read()

# Methods to add
solicitation_methods = '''
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
'''

# Check if methods already exist
if 'def get_all_solicitations(self, limit' not in content:
    # Append before the final newline
    if content.endswith('\n'):
        content = content[:-1] + solicitation_methods + '\n'
    else:
        content = content + solicitation_methods

    # Write back
    with open('database_manager.py', 'w') as f:
        f.write(content)

    print("✅ Solicitation methods added successfully!")
    print(f"File now has {len(content.splitlines())} lines")
else:
    print("⚠️ Methods already exist, skipping")
