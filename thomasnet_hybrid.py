#!/usr/bin/env python3
"""
HYBRID Semi-Automated ThomasNet RFQ
User does: Search + Select Vendors + Click "Contact Suppliers" (manual)
Script does: Fill Form + Submit (automated)
"""
import sys
import os
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from playwright.sync_api import sync_playwright
from ai_agents.OutreachAgent.form_filler import IDENTITY

def hybrid_rfq_workflow(product_name, product_details):
    """
    Hybrid approach:
    1. USER manually: Search ThomasNet, select 5 vendors, click "Contact Suppliers"
    2. SCRIPT automatically: Fill the RFQ form and submit
    """
    
    print("="*60)
    print("HYBRID ThomasNet RFQ Workflow")
    print("="*60)
    print("\n📋 YOUR MANUAL TASKS:")
    print("1. Open ThomasNet.com in the browser that will open")
    print(f"2. Search for: {product_name}")
    print("3. Select 5 vendors (click checkboxes)")
    print("4. Click 'Contact Selected Suppliers' or 'Request Quote'")
    print("\n⏳ After you click the button, the script will:")
    print("✓ Detect the RFQ form")
    print("✓ Auto-fill all fields")
    print("✓ Submit the request")
    print("\n" + "="*60)
    
    input("\nPress ENTER when ready to start...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        context = browser.new_context(viewport={'width': 1366, 'height': 768})
        page = context.new_page()
        
        # Navigate to ThomasNet
        print("\n✓ Opening ThomasNet...")
        page.goto("https://www.thomasnet.com/suppliers", timeout=60000)
        
        # Wait for user to complete manual tasks
        print("\n" + "!"*60)
        print("👉 NOW:")
        print(f"1. Search for '{product_name}'")
        print("2. Select 5 vendors")
        print("3. Click 'Contact Suppliers'")
        print("\n⏳ Script will auto-continue when form appears...")
        print("!"*60 + "\n")
        
        # Wait for RFQ form to appear (detect common form elements)
        print("Waiting for RFQ form...")
        try:
            # Wait for form with email or textarea (indicates RFQ form)
            page.wait_for_selector('form textarea, form input[type="email"]', timeout=300000)  # 5 min
            print("✓ RFQ form detected!\n")
            time.sleep(2)
        except:
            print("✗ Form not detected within 5 minutes. Did you click 'Contact Suppliers'?")
            browser.close()
            return {'success': False, 'error': 'Form timeout'}
        
        # AUTO-FILL FORM
        print("🤖 Auto-filling form...")
        
        form_fields = {
            'name': ['input[name*="name"]', 'input[id*="name"]', 'input[placeholder*="Name"]'],
            'email': ['input[type="email"]', 'input[name*="email"]', 'input[id*="email"]'],
            'phone': ['input[type="tel"]', 'input[name*="phone"]', 'input[id*="phone"]'],
            'company': ['input[name*="company"]', 'input[id*="company"]'],
            'message': ['textarea', 'textarea[name*="message"]', 'textarea[id*="comment"]']
        }
        
        def fill_field(field_name, value, selectors_list):
            for sel in selectors_list:
                try:
                    field = page.query_selector(sel)
                    if field and field.is_visible():
                        field.fill(value)
                        print(f"  ✓ Filled {field_name}")
                        return True
                except: pass
            print(f"  ⚠ Could not find field: {field_name}")
            return False
        
        # Fill all fields
        fill_field('name', IDENTITY['FULL_NAME'], form_fields['name'])
        fill_field('email', IDENTITY['EMAIL'], form_fields['email'])
        fill_field('phone', IDENTITY['PHONE'], form_fields['phone'])
        fill_field('company', IDENTITY['COMPANY'], form_fields['company'])
        
        # Generate message
        message = f"""Request for Quote - {product_name}

Product/Service Required: {product_name}
Quantity: {product_details.get('quantity', 'To be determined')}
Delivery Timeline: {product_details.get('due_date', 'ASAP')}

We are evaluating suppliers for this requirement. Please provide:
- Itemized pricing
- Lead time  
- Warranty information

Contact: {IDENTITY['EMAIL']}
"""
        fill_field('message', message, form_fields['message'])
        
        # SUBMIT
        print("\n📤 Submitting form...")
        time.sleep(2)  # Visual confirmation
        
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Send")'
        ]
        
        submitted = False
        for sel in submit_selectors:
            try:
                submit_btn = page.query_selector(sel)
                if submit_btn and submit_btn.is_visible():
                    submit_btn.click()
                    submitted = True
                    print("✓ Form submitted!")
                    break
            except: pass
        
        if not submitted:
            print("⚠ Could not find submit button. Please submit manually.")
        else:
            time.sleep(3)
            # Check for confirmation
            content = page.content().lower()
            if "thank" in content or "success" in content or "sent" in content:
                print("✓ Confirmation detected!")
        
        print("\nKeeping browser open for 10 seconds...")
        time.sleep(10)
        browser.close()
        
        return {
            'success': submitted,
            'vendors_contacted': 5,  # User selected manually
            'confirmation_message': 'RFQ submitted via hybrid workflow'
        }


if __name__ == "__main__":
    test_product = {
        'product_name': 'Industrial Bolts',
        'notice_id': 'TEST-001',
        'quantity': '1000 units',
        'due_date': 'March 15, 2026'
    }
    
    result = hybrid_rfq_workflow(test_product['product_name'], test_product)
    
    print("\n" + "="*60)
    print("FINAL RESULT")
    print("="*60)
    print(f"Success: {result['success']}")
    print(f"Vendors Contacted: {result.get('vendors_contacted', 'N/A')}")
    print("="*60)
