#!/usr/bin/env python3
"""
Populate the database with existing RFQ files
"""
import os
import glob
import json
import sqlite3
from datetime import datetime
from pathlib import Path

def extract_contract_id(filename):
    """Extract contract ID from filename like 'id_RFQ_TYPE.docx'"""
    # Remove extension
    name_without_ext = os.path.splitext(filename)[0]
    # Split by _RFQ_ and take first part
    if '_RFQ_' in name_without_ext:
        return name_without_ext.split('_RFQ_')[0]
    return None

def extract_rfq_type(filename):
    """Extract RFQ type from filename"""
    name_without_ext = os.path.splitext(filename)[0]
    if '_RFQ_' in name_without_ext:
        parts = name_without_ext.split('_RFQ_')
        if len(parts) > 1:
            # Take the part after _RFQ_ and before .docx extension
            rfq_part = parts[1]
            # Remove any additional extensions or suffixes
            return rfq_part.upper() if rfq_part in ['PRODUCT', 'SERVICE'] else 'UNKNOWN'
    return 'UNKNOWN'

def get_rfq_content_mock(contract_id, rfq_type):
    """Generate mock RFQ content for database population"""
    return f"""# REQUEST FOR QUOTE ({rfq_type})

**Contract ID:** {contract_id}
**Date:** {datetime.now().strftime('%Y-%m-%d')}
**Item Requested:** Industrial Equipment for Government Use

## Scope of Work
The Camp Sable, LLC requests quotations for the supply and delivery of industrial equipment as specified in this RFQ.

## Requirements
1. Equipment must meet all applicable federal standards
2. Delivery within 30 days of award
3. Price must include delivery to specified location
4. Warranty of minimum 1 year on all equipment

## Submission Instructions
Quotations must be submitted by the specified deadline to:
Camp Sable, LLC
Attn: Procurement Department
Email: bobbysmitty078@gmail.com

## Contact Information
For questions regarding this RFQ, please contact:
Bobby Smitty
Phone: +1 (720) 980-6080
Email: bobbysmitty078@gmail.com

---
*This is a mock RFQ generated for database population purposes.*
"""

def populate_database():
    """Populate database with RFQ file information"""
    
    # Use the fresh database we created
    db_path = 'rebusiness_automation_fresh.db'
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Find all RFQ files
    rfq_pattern = 'rfq_downloads/2*/*_RFQ_PRODUCT.docx'
    rfq_files = glob.glob(rfq_pattern)
    
    print(f"Found {len(rfq_files)} RFQ files to process")
    
    processed = 0
    skipped = 0
    
    for rfq_file in rfq_files:
        try:
            filename = os.path.basename(rfq_file)
            contract_id = extract_contract_id(filename)
            rfq_type = extract_rfq_type(filename)
            
            if not contract_id:
                print(f"Skipping {filename}: Could not extract contract ID")
                skipped += 1
                continue
                
            # Check if we already have this contract_id
            cursor.execute("SELECT 1 FROM solicitations WHERE contract_id = ?", (contract_id,))
            if cursor.fetchone():
                print(f"Skipping {filename}: Contract ID {contract_id} already exists")
                skipped += 1
                continue
            
            # Generate mock data for the solicitation
            title = f"Request for Quote {contract_id} - {rfq_type}"
            description = f"Government procurement opportunity for {rfq_type.lower()} equipment"
            
            # Insert into solicitations table
            cursor.execute("""
                INSERT OR IGNORE INTO solicitations 
                (contract_id, url, title, description, location, product_requirements, 
                 analysis_summary, data, review_status, extraction_confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                contract_id,
                f"https://sam.gov/opp/{contract_id}",
                title,
                description,
                "USA",
                f"Industrial {rfq_type} Equipment",
                json.dumps({"extracted": True, "confidence": 0.9}),
                json.dumps({"source": "file_population", "filename": filename}),
                'pending',
                0.85,
                datetime.now()
            ))
            
            # Insert into rfq_outputs table
            rfq_content = get_rfq_content_mock(contract_id, rfq_type)
            cursor.execute("""
                INSERT OR IGNORE INTO rfq_outputs 
                (contract_id, rfq_type, rfq_content, format, generated_date, sent_to_vendor)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                contract_id,
                rfq_type,
                rfq_content,
                'docx',
                datetime.now(),
                0  # Not sent yet
            ))
            
            print(f"Processed: {filename} -> Contract ID: {contract_id}, Type: {rfq_type}")
            processed += 1
            
        except Exception as e:
            print(f"Error processing {rfq_file}: {e}")
            skipped += 1
    
    conn.commit()
    conn.close()
    
    print(f"\nSummary:")
    print(f"  Processed: {processed} RFQ files")
    print(f"  Skipped: {skipped} files")
    
    # Show final counts
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM solicitations")
    solicitation_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM rfq_outputs WHERE sent_to_vendor = 0")
    pending_rfq_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"  Total solicitations in DB: {solicitation_count}")
    print(f"  Pending RFQs (not sent): {pending_rfq_count}")

if __name__ == "__main__":
    populate_database()
