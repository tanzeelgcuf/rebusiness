import sqlite3
import os
import time
from database_manager import DatabaseManager

def monitor_vendors():
    db = DatabaseManager()
    
    print("Monitoring 'vendors' table for new Thomasnet entries...")
    try:
        while True:
            conn = db._connect_db()
            cursor = conn.cursor()
            
            # Count total vendors
            cursor.execute("SELECT COUNT(*) FROM vendors")
            total_vendors = cursor.fetchone()[0]
            
            # Count vendors with source containing 'ThomasNet' (if we stored it in notes or summary)
            # Our ThomasNetAgent implementation puts "Sourced via ThomasNet" in past_performance_summary
            cursor.execute("SELECT COUNT(*) FROM vendors WHERE past_performance_summary LIKE '%ThomasNet%'")
            thomasnet_vendors = cursor.fetchone()[0]
            
            # Get latest 5 vendors
            cursor.execute("SELECT name, email, website, past_performance_summary FROM vendors ORDER BY rowid DESC LIMIT 5")
            latest_vendors = cursor.fetchall()
            
            os.system('clear')
            print(f"=== Vendor Monitor ===")
            print(f"Total Vendors: {total_vendors}")
            print(f"ThomasNet Vendors: {thomasnet_vendors}")
            print("\nLatest 5 Entries:")
            for v in latest_vendors:
                print(f"- {v[0]} | {v[1]} | {v[2]} | {v[3]}")
                
            conn.close()
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nStopping monitor.")

if __name__ == "__main__":
    monitor_vendors()
