import sqlite3
import os

DB_PATH = 'rebusiness_automation.db'
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Initial Count:", cursor.execute("SELECT COUNT(*) FROM solicitations").fetchone()[0])

# Get last 10 added
rows = cursor.execute("SELECT contract_id, title, created_at FROM solicitations ORDER BY rowid DESC LIMIT 10").fetchall()
print("\nLast 10 entries:")
for r in rows:
    print(r)

# Delete items that were likely part of the failed batch (checked against logs)
ids_to_delete = ['89316097f7', 'a948c170ba', '401b5b13ce', 'f27ce85717', 'd800d19ddc', 'b7a76b1322', 'ea25a0952f']
print(f"\nDeleting {len(ids_to_delete)} specific IDs: {ids_to_delete}")

placeholders = ','.join('?' for _ in ids_to_delete)
cursor.execute(f"DELETE FROM solicitations WHERE contract_id IN ({placeholders})", ids_to_delete)
conn.commit()

print("Final Count:", cursor.execute("SELECT COUNT(*) FROM solicitations").fetchone()[0])
conn.close()
