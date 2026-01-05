#!/usr/bin/env python3
"""
Comprehensive Email Template Population Test
Tests both Product and Service email templates against real database data
to ensure 100% field population as per Claude Vendor List.odt and Claude Services List.odt
"""

import sqlite3
import json
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from run_email_campaign import format_product_email_body, format_service_email_body

DB_PATH = "rebusiness_automation.db"

def test_email_population():
    print("="*80)
    print("EMAIL TEMPLATE POPULATION VERIFICATION")
    print("="*80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Test 1: Find a Product solicitation with attachments
    print("\n[TEST 1] Finding Product Solicitation with Attachments...")
    cursor.execute("""
        SELECT s.contract_id, s.title, s.analysis_summary, s.data, s.url,
               p.product_name, p.quantity, p.specifications, p.description, p.id
        FROM solicitations s
        JOIN products p ON s.contract_id = p.contract_id
        JOIN attachments a ON s.contract_id = a.contract_id
        WHERE s.analysis_summary IS NOT NULL
        AND s.analysis_summary LIKE '%"solicitation_category"%Product%'
        LIMIT 1
    """)
    
    product_row = cursor.fetchone()
    
    if product_row:
        print(f"✅ Found Product: {product_row[1][:60]}...")
        
        subject, plain, html = format_product_email_body(
            sol_id=product_row[0],
            sol_title=product_row[1],
            product_name=product_row[5],
            quantity=product_row[6],
            specs=product_row[7],
            delivery_loc_json=None,
            timeline=None,
            description=product_row[8],
            due_date_str=None,
            sol_url=product_row[4],
            analysis_json=product_row[2]
        )
        
        print("\n" + "="*80)
        print("PRODUCT EMAIL TEMPLATE OUTPUT")
        print("="*80)
        print(f"\nSubject: {subject}\n")
        print(plain)
        print("\n" + "="*80)
        
        # Validate Required Fields (Claude Vendor List.odt)
        required_fields = [
            "Agency Issuing RFQ",
            "Type of Contract",
            "Set-Aside Type",
            "NAICS Code",
            "Item Requested",
            "Manufacturer CAGE",
            "Packaging Requirements",
            "Inspection & Testing",
            "Delivery Requirements",
            "Technical Data Package"
        ]
        
        print("\n[VALIDATION] Checking Required Fields...")
        missing = []
        for field in required_fields:
            if field not in plain:
                missing.append(field)
                print(f"  ❌ MISSING: {field}")
            else:
                print(f"  ✅ FOUND: {field}")
        
        if missing:
            print(f"\n⚠️  WARNING: {len(missing)} fields missing from Product template!")
        else:
            print(f"\n✅ SUCCESS: All required Product fields present!")
    else:
        print("⚠️  No Product solicitations with attachments found")
    
    # Test 2: Find a Service solicitation
    print("\n\n[TEST 2] Finding Service Solicitation...")
    cursor.execute("""
        SELECT s.contract_id, s.title, s.analysis_summary, s.data, s.url,
               p.product_name, p.quantity, p.specifications, p.description, p.id
        FROM solicitations s
        JOIN products p ON s.contract_id = p.contract_id
        WHERE s.analysis_summary IS NOT NULL
        AND (s.title LIKE '%service%' OR s.title LIKE '%maintenance%' OR s.title LIKE '%repair%')
        LIMIT 1
    """)
    
    service_row = cursor.fetchone()
    
    if service_row:
        print(f"✅ Found Service: {service_row[1][:60]}...")
        
        subject, plain, html = format_service_email_body(
            sol_id=service_row[0],
            sol_title=service_row[1],
            product_name=service_row[5],
            quantity=service_row[6],
            specs=service_row[7],
            delivery_loc_json=None,
            timeline=None,
            description=service_row[8],
            due_date_str=None,
            sol_url=service_row[4],
            analysis_json=service_row[2]
        )
        
        print("\n" + "="*80)
        print("SERVICE EMAIL TEMPLATE OUTPUT")
        print("="*80)
        print(f"\nSubject: {subject}\n")
        print(plain)
        print("\n" + "="*80)
        
        # Validate Required Fields (Claude Services List.odt)
        required_fields = [
            "General Overview",
            "Scope of Work",
            "Key Requirements",
            "Security / Compliance",
            "Wage & Labor",
            "Insurance Requirements",
            "Contract Clauses",
            "Bid Submission Instructions",
            "Post-Award Responsibilities"
        ]
        
        print("\n[VALIDATION] Checking Required Fields...")
        missing = []
        for field in required_fields:
            if field not in plain:
                missing.append(field)
                print(f"  ❌ MISSING: {field}")
            else:
                print(f"  ✅ FOUND: {field}")
        
        if missing:
            print(f"\n⚠️  WARNING: {len(missing)} fields missing from Service template!")
        else:
            print(f"\n✅ SUCCESS: All required Service fields present!")
    else:
        print("⚠️  No Service solicitations found")
    
    # Test 3: Check for "Information not provided" fallbacks
    print("\n\n[TEST 3] Checking Fallback Quality...")
    if product_row:
        _, plain, _ = format_product_email_body(
            sol_id=product_row[0],
            sol_title=product_row[1],
            product_name=product_row[5],
            quantity=product_row[6],
            specs=product_row[7],
            delivery_loc_json=None,
            timeline=None,
            description=product_row[8],
            due_date_str=None,
            sol_url=product_row[4],
            analysis_json=product_row[2]
        )
        
        fallback_count = plain.count("Information not provided in solicitation")
        print(f"  Fallback messages: {fallback_count}")
        
        if fallback_count > 10:
            print(f"  ⚠️  HIGH fallback count - data extraction may be incomplete")
        elif fallback_count > 5:
            print(f"  ⚠️  MODERATE fallback count - acceptable but could be improved")
        else:
            print(f"  ✅ LOW fallback count - good data extraction")
    
    conn.close()
    
    print("\n" + "="*80)
    print("VERIFICATION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    test_email_population()
