import sqlite3
import os
from database_manager import DatabaseManager

def check_downloaded_attachments():
    db_manager = DatabaseManager()
    conn = db_manager._connect_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT contract_id, title FROM solicitations")
        solicitations = cursor.fetchall()

        print("\n--- Downloaded Attachments Report ---")
        print(f"{ 'Contract ID':<35} | { 'Title':<50} | { 'Attachments Count':<20}")
        print("-" * 108)

        for sol in solicitations:
            contract_id = sol['contract_id']
            # Handle cases where title might be None
            title = sol['title'] if sol['title'] is not None else "N/A" 
            cursor.execute("SELECT COUNT(*) FROM attachments WHERE contract_id = ?", (contract_id,))
            count = cursor.fetchone()[0]
            print(f"{contract_id:<35} | {title:<50} | {count:<20}")
        
        print("-" * 108)
        print("Note: 'Downloaded 0 files.' in the output log indicates that the DescriptionDownloaderAgent was unable to find or process attachments for that specific solicitation, not that the report below is incorrect.")

    except Exception as e:
        print(f"An error occurred while checking attachments: {e}")
    finally:
        db_manager._close_db()

if __name__ == "__main__":
    check_downloaded_attachments()
