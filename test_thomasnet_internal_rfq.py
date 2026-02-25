#!/usr/bin/env python3
"""
Test script for ThomasNet Internal RFQ workflow
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent

def test_internal_rfq():
    """Test the new ThomasNet Internal RFQ workflow"""
    print("="*60)
    print("Testing ThomasNet Internal RFQ System")
    print("="*60)
    
    # Test product
    test_product = {
        'product_name': 'Industrial Bolts',
        'notice_id': 'TEST-001',
        'quantity': '1000 units',
        'due_date': 'March 15, 2026'
    }
    
    agent = ThomasNetAgent()
    
    print("\nInitiating RFQ workflow...")
    print(f"Product: {test_product['product_name']}")
    print(f"Target: 5 vendors\n")
    
    result = agent.select_vendors_and_submit_rfq(test_product, limit=5)
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"Success: {result['success']}")
    print(f"Vendors Contacted: {result['vendors_contacted']}")
    print(f"Confirmation: {result['confirmation_message']}")
    if result['error']:
        print(f"Error: {result['error']}")
    print("="*60)
    
    return result

if __name__ == "__main__":
    test_internal_rfq()
