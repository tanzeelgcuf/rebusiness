#!/usr/bin/env python3
"""
Test Manufacturer Workflow
Tests the complete manufacturer price discovery workflow on a sample product.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database_manager import DatabaseManager
from ai_agents.ManufacturerAgent.manufacturer_agent import ManufacturerAgent
from ai_agents.PriceRequestAgent.price_request_agent import PriceRequestAgent

def test_manufacturer_workflow():
    """Test the complete workflow with a sample product."""
    
    print("=" * 80)
    print("TESTING MANUFACTURER PRICE DISCOVERY WORKFLOW")
    print("=" * 80)
    
    db = DatabaseManager()
    
    # Step 1: Get a product from database
    print("\n--- Step 1: Getting product from database ---")
    products = db.get_products_by_contract("ef388f3d2d77443fa4d04d3974d4e2de")  # Fuel Management Panels
    
    if not products:
        print("No products found. Run extract_products.py first.")
        return
    
    product = products[0]
    print(f"Product: {product['product_name']}")
    print(f"Contract: {product['contract_id']}")
    print(f"Quantity: {product['quantity']}")
    
    # Step 2: Find manufacturers
    print("\n--- Step 2: Finding manufacturers ---")
    mfg_agent = ManufacturerAgent()
    
    manufacturers = mfg_agent.find_manufacturers(
        product_name=product['product_name'],
        product_specs=product.get('specifications')
    )
    
    if not manufacturers:
        print("No manufacturers found.")
        mfg_agent.close()
        return
    
    print(f"\nFound {len(manufacturers)} manufacturers:")
    for i, mfg in enumerate(manufacturers[:3], 1):  # Show top 3
        print(f"{i}. {mfg['name']} - {mfg['website']}")
    
    # Step 3: Get contact info for first manufacturer
    print("\n--- Step 3: Getting contact information ---")
    mfg = manufacturers[0]
    contact_info = mfg_agent.get_manufacturer_contact_info(mfg['name'], mfg['website'])
    mfg.update(contact_info)
    
    print(f"Manufacturer: {mfg['name']}")
    print(f"Email: {mfg.get('email', 'Not found')}")
    print(f"Phone: {mfg.get('phone', 'Not found')}")
    print(f"State: {mfg.get('state', 'Not found')}")
    
    # Step 4: Save manufacturer to database
    print("\n--- Step 4: Saving manufacturer to database ---")
    mfg_id = mfg_agent.save_manufacturer(mfg)
    
    if not mfg_id:
        print("Failed to save manufacturer.")
        mfg_agent.close()
        return
    
    print(f"Manufacturer saved with ID: {mfg_id}")
    
    # Step 5: Send price request (if email found)
    if mfg.get('email'):
        print("\n--- Step 5: Sending price request ---")
        
        # Uncomment to actually send email:
        # price_agent = PriceRequestAgent()
        # request_id = price_agent.send_price_request(
        #     manufacturer_id=mfg_id,
        #     product_id=product['id'],
        #     manufacturer_email=mfg['email'],
        #     manufacturer_name=mfg['name'],
        #     product_name=product['product_name'],
        #     product_specs=product.get('specifications'),
        #     quantity=product.get('quantity')
        # )
        # print(f"Price request sent (Request ID: {request_id})")
        
        print(f"Would send price request to: {mfg['email']}")
        print("(Uncomment code above to actually send)")
    else:
        print("\n--- Step 5: Skipped (no email found) ---")
    
    # Cleanup
    mfg_agent.close()
    
    print("\n" + "=" * 80)
    print("WORKFLOW TEST COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review manufacturer data in database")
    print("2. Uncomment email sending code to send actual requests")
    print("3. Wait for manufacturer responses")
    print("4. Parse price lists when received")

if __name__ == "__main__":
    test_manufacturer_workflow()
