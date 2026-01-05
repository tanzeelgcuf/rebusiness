
import sqlite3
import json
import os
from database_manager import DatabaseManager

def list_flagged_solicitations():
    db = DatabaseManager()
    conn = db._connect_db()
    cursor = conn.cursor()
    
    print("\n=== SOLICITATIONS FLAGGED FOR MANUAL REVIEW ===\n")
    
    try:
        cursor.execute("""
            SELECT contract_id, title, extraction_confidence, analysis_summary 
            FROM solicitations 
            WHERE review_status = 'flagged'
        """)
        flagged = cursor.fetchall()
        
        if not flagged:
            print("No solicitations currently flagged for review.")
            return

        for row in flagged:
            cid = row['contract_id']
            title = row['title']
            conf = row['extraction_confidence']
            analysis_json = row['analysis_summary']
            
            print(f"ID: {cid}")
            print(f"Title: {title}")
            print(f"Confidence: {conf}")
            
            # Identify what's missing
            try:
                data = json.loads(analysis_json)
                missing = []
                
                # Check Specs
                specs = data.get('specifications', {})
                if "Information not provided" in specs.get('manufacturer_cage', ''): missing.append("CAGE")
                if "Information not provided" in specs.get('manufacturer_part_number', ''): missing.append("Part#")
                
                # Check Ship To
                delivery = data.get('delivery_requirements', {})
                ship = delivery.get('ship_to_address', {})
                if isinstance(ship, dict):
                    if "Information not provided" in ship.get('city', ''): missing.append("Ship-To")
                
                print(f"Missing Critical Data: {', '.join(missing)}")
                print("-" * 50)
                
            except json.JSONDecodeError:
                print("Error: Invalid JSON analysis data")
                
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        db._close_db()

if __name__ == "__main__":
    list_flagged_solicitations()
