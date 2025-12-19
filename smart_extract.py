#!/usr/bin/env python3
"""
Smart Product Extractor & Filter
Filters out service contracts and safely extracts products from recent solicitations,
handling API rate limits.
"""

import sys
import os
import time
import json
import sqlite3
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database_manager import DatabaseManager, DATABASE_NAME
from extract_products import ProductExtractor
from ai_agents.SolicitationAnalysisAgent.solicitation_analysis import analyze_solicitation

# Keywords to identify service/maintenance contracts
SERVICE_KEYWORDS = [
    'service', 'maintenance', 'repair', 'install', 'training', 
    'consulting', 'lease', 'rental', 'construction', 'janitorial',
    'landscaping', 'security guard', 'pest control', 'waste removal',
    'laundry', 'towing', 'hvac', 'demolition'
]

# Keywords that strongly imply goods/products
PRODUCT_KEYWORDS = [
    'supply', 'deliver', 'furnish', 'equipment', 'parts', 
    'hardware', 'software', 'materials', 'components', 'assembly',
    'kit', 'unit', 'fob', 'brand name', 'equal'
]

def is_service_contract(title, description):
    """
    Determine if a solicitation is likely a service contract based on keywords.
    Returns True if service, False if product/mixed.
    """
    text = (title + " " + (description or "")).lower()
    
    # Check for service keywords
    is_service = any(keyword in text for keyword in SERVICE_KEYWORDS)
    
    # Check for product keywords which might override or qualify
    has_product = any(keyword in text for keyword in PRODUCT_KEYWORDS)
    
    # If it has product keywords, we might want to keep it even if it says "repair" 
    # (e.g. "Repair Parts"), but for now we want to be strict to save quota.
    # Let's use a simple heuristic: if it hits service keywords and NOT strong product keywords, skip.
    
    if is_service and not has_product:
        return True
        
    return False

def smart_extract():
    print("=" * 80)
    print("SMART PRODUCT EXTRACTION & FILTERING")
    print("=" * 80)
    
    db = DatabaseManager()
    extractor = ProductExtractor()
    
    # 1. Fetch recent solicitations
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Fetch ones from the last few days
    cursor.execute("""
        SELECT * FROM solicitations 
        WHERE date(created_at) >= '2025-12-16'
    """)
    solicitations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    print(f"Found {len(solicitations)} recent solicitations to process.")
    
    processed_count = 0
    skipped_count = 0
    reanalyzed_count = 0
    products_found = 0
    
    for i, sol in enumerate(solicitations):
        contract_id = sol['contract_id']
        title = sol['title']
        description = sol['description']
        analysis = sol['analysis_summary']
        
        print(f"\nProcessing [{i+1}/{len(solicitations)}]: {title[:60]}...")
        
        # 2. Filter out services
        if is_service_contract(title, description):
            print(f"  ⏭️  Skipping: Likely SERVICE/MAINTENANCE contract.")
            skipped_count += 1
            continue
            
        # 3. Check if analysis is needed
        needs_analysis = False
        if not analysis:
            needs_analysis = True
        elif "Error extraction" in analysis:
            needs_analysis = True
        elif "Insufficient details" in analysis:
            # Maybe retry if we think we can do better, but usually this is terminal without attachments
            pass
            
        if needs_analysis:
            print(f"  🔄 Re-analyzing (Previous: {analysis[:30] if analysis else 'None'})...")
            
            # Rate limiting delay
            time.sleep(2.5) 
            
            try:
                new_analysis, confidence = analyze_solicitation(sol)
                
                # Simple check if we hit rate limit again
                if "Resource has been exhausted" in new_analysis:
                    print("  ❌ Rate limit hit again. Initial backoff...")
                    time.sleep(10) # Longer backoff
                    new_analysis, confidence = analyze_solicitation(sol)
            except Exception as e:
                print(f"  ❌ Critical analysis error: {e}")
                new_analysis = f"Error extraction: {e}"
                confidence = 0.0

            # Update DB
            try:
                # Use independent connection to avoid messing up DatabaseManager state
                update_conn = sqlite3.connect(DATABASE_NAME)
                cursor = update_conn.cursor()
                cursor.execute("""
                    UPDATE solicitations 
                    SET analysis_summary = ?, extraction_confidence = ?
                    WHERE contract_id = ?
                """, (new_analysis, confidence, contract_id))
                update_conn.commit()
                update_conn.close()
            except Exception as e:
                print(f"  ❌ DB Error updating solicitation: {e}")
            
            analysis = new_analysis
            reanalyzed_count += 1
        
        # 4. Extract Products
        try:
             if analysis and "Error extraction" not in analysis:
                products = extractor._parse_products_from_analysis(analysis, title)
                
                if products:
                    print(f"  ✅ Found {len(products)} product(s)")
                    for product in products:
                         try:
                            product_id = db.add_product(
                                contract_id=contract_id,
                                product_name=product['name'],
                                description=product.get('description'),
                                specifications=product.get('specifications'),
                                quantity=product.get('quantity'),
                                naics_code=product.get('naics_code')
                            )
                            if product_id:
                                products_found += 1
                         except Exception as e:
                             print(f"    ⚠️ Error saving product: {e}")
                else:
                    print("  🔸 No products parsed from analysis.")
             else:
                 print("  ❌ Analysis failed or still empty.")
        except Exception as e:
            print(f"  ❌ Extraction error: {e}")

        processed_count += 1
        
        # Every 10 items, print a progress summary
        if processed_count % 10 == 0:
            print(f"\n--- Progress: {processed_count} processed, {products_found} products found so far ---")

    print("\n" + "=" * 80)
    print(f"COMPLETE")
    print(f"Total Processed: {len(solicitations)}")
    print(f"Skipped (Services): {skipped_count}")
    print(f"Re-analyzed: {reanalyzed_count}")
    print(f"Products Extracted: {products_found}")
    print("=" * 80)

if __name__ == "__main__":
    smart_extract()
