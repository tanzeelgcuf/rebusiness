#!/usr/bin/env python3
"""
Re-analyze existing solicitations using the new SAMGovExtractor (Strict Pipeline).
Updates the 'analysis_summary' column in the database with the FULL JSON extracted data.
"""

import sqlite3
import sys
import os
import json
import logging
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from ai_agents.SAMGovExtractor.sam_gov_extractor import SAMGovExtractor

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Reanalyzer")

DB_PATH = "rebusiness_automation.db"

def get_solicitations(target_id=None, limit=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if target_id:
        cursor.execute("SELECT contract_id, title, url, data FROM solicitations WHERE contract_id = ?", (target_id,))
    else:
        # Get solicitations that have attachments
        query = """
            SELECT DISTINCT s.contract_id, s.title, s.url, s.data
            FROM solicitations s
            INNER JOIN attachments a ON s.contract_id = a.contract_id
            WHERE s.data IS NOT NULL
            GROUP BY s.contract_id
            ORDER BY s.contract_id DESC
        """
        if limit and limit > 0:
            query += f" LIMIT {limit}"
        cursor.execute(query)
        
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_attachments(contract_id):
    """Fetch and read attachments from disk."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT file_name, file_path FROM attachments WHERE contract_id = ?", (contract_id,))
    rows = cursor.fetchall()
    conn.close()
    
    attachments = []
    import PyPDF2
    
    for row in rows:
        f_path = row['file_path']
        f_name = row['file_name']
        
        if not os.path.exists(f_path):
            logger.warning(f"File missing on disk: {f_path}")
            continue
            
        content = ""
        try:
            if f_path.lower().endswith('.pdf'):
                with open(f_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        content += page.extract_text() + "\n"
            else:
                with open(f_path, 'r', errors='ignore') as f:
                    content = f.read()
            
            if content.strip():
                 attachments.append({'filename': f_name, 'content': content})
        except Exception as e:
            logger.warning(f"Error reading {f_name}: {e}")
            
    return attachments

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--contract_id', help='Specific contract ID to re-analyze')
    parser.add_argument('--limit', type=int, default=10, help='Limit number of records')
    args = parser.parse_args()
    
    # Initialize Extractor
    try:
        extractor = SAMGovExtractor()
    except Exception as e:
        logger.error(f"Failed to init extractor: {e}")
        return

    solicitations = get_solicitations(args.contract_id, args.limit)
    logger.info(f"Found {len(solicitations)} solicitations to process.")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    success_count = 0
    
    for row in solicitations:
        cid = row['contract_id']
        logger.info(f"Processing: {cid}")
        
        # 1. Get Attachments
        atts = get_attachments(cid)
        if not atts:
            logger.warning(f"  No readable attachments for {cid}. Skipping.")
            continue
            
        # 2. Extract
        # Use existing 'data' as main text source (it contains the scraped HTML usually or JSON dump of it)
        main_text = str(row['data']) 
        
        try:
            result = extractor.extract_solicitation(main_text, atts)
            
            # 3. Save Result
            # IMPORTANT: Save the FULL JSON into 'analysis_summary' so run_email_campaign.py can use it
            json_str = json.dumps(result)
            cursor.execute("UPDATE solicitations SET analysis_summary = ? WHERE contract_id = ?", (json_str, cid))
            conn.commit()
            
            status = result.get('extraction_status', 'UNKNOWN')
            logger.info(f"  ✅ Complete. Status: {status}")
            if status == "SUCCESS":
                success_count += 1
            else:
                logger.warning(f"  ⚠️ Validation Errors: {result.get('validation_errors')}")
                
        except Exception as e:
            logger.error(f"  ❌ Error processing {cid}: {e}")
            
    conn.close()
    logger.info(f"Done. Success Count: {success_count}/{len(solicitations)}")

if __name__ == "__main__":
    main()
