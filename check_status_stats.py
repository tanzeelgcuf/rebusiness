import sqlite3
from database_manager import DatabaseManager

db = DatabaseManager()
conn = db._connect_db()
cursor = conn.cursor()

print("--- Sourcing Status ---")
cursor.execute("SELECT status, COUNT(*) FROM product_sourcing_status GROUP BY status")
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]}")

print("\n--- Manufacturer Requests ---")
cursor.execute("SELECT status, COUNT(*) FROM manufacturer_requests GROUP BY status")
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]}")

# Check for stuck items (sourcing status but last_sourcing_date > 1 hour ago? - assume interruption for now)
print("\n--- Potential Stalled Items ---")
cursor.execute("SELECT product_id FROM product_sourcing_status WHERE status='sourcing'")
stuck = cursor.fetchall()
print(f"Items stuck in 'sourcing': {[s[0] for s in stuck]}")

db._close_db()
