#!/usr/bin/env python3
"""
Comprehensive End-to-End Test
Tests the complete automation pipeline with live dashboard tracking:
1. Scrape solicitations from sam.gov
2. Generate RFQs (.docx files)
3. Submit to ThomasNet vendors
4. Track everything on the dashboard

BEFORE RUNNING:
1. Start the dashboard in another terminal:
   cd dashboard && python3 app.py

2. Open dashboard in browser:
   http://localhost:5000

3. Ensure Chrome is running with remote debugging:
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 \
     --user-data-dir="/tmp/chrome-debug"

4. Sign in to ThomasNet in that Chrome window
"""

import sys
import os
import time
import glob
from datetime import datetime

# Add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent
from database_manager import DatabaseManager
from rfq_validator import RFQValidator

def print_banner(text):
    """Print a nice banner"""
    print("\n" + "="*80)
    print(f" {text}")
    print("="*80 + "\n")

def wait_for_user(message="Press ENTER to continue..."):
    """Wait for user confirmation"""
    input(f"\n{message}")

def test_complete_workflow():
    """Run complete end-to-end test"""
    
    print_banner("🚀 COMPREHENSIVE END-TO-END TEST")
    print("This test will:")
    print("  1. Scrape 1 solicitation from sam.gov")
    print("  2. Generate an RFQ (.docx)")
    print("  3. Submit to ThomasNet vendors")
    print("  4. Track everything on the dashboard")
    print("\nYou can monitor all activity live on the dashboard at:")
    print("  👉 http://localhost:5000")
    
    wait_for_user("\n📊 Make sure the dashboard is running, then press ENTER to start...")
    
    # Initialize
    db = DatabaseManager()
    scraper = SamGovAgent()
    reader = AttachmentReaderAgent()
    thomasnet = ThomasNetAgent()
    validator = RFQValidator()
    
    # ========================================================================
    # STEP 1: Scrape Solicitation
    # ========================================================================
    print_banner("STEP 1: Scraping Solicitation from sam.gov")
    print("Searching for: 'industrial equipment'")
    print("Pages: 1 (will get ~10 solicitations)")
    
    search_results = scraper.search_solicitations(
        keywords="industrial equipment",
        start_page=1,
        num_pages=1
    )
    
    if not search_results:
        print("❌ No solicitations found!")
        return False
    
    print(f"\n✅ Found {len(search_results)} solicitations")
    
    # Pick first PRODUCT solicitation
    product_sol = None
    for sol in search_results:
        sol_details = scraper.extract_solicitation_details(sol['url'])
        if sol_details:
            # Save to database
            db.add_solicitation(
                contract_id=sol_details['contract_id'],
                url=sol_details['url'],
                title=sol_details.get('title', ''),
                description=sol_details.get('description', ''),
                location=sol_details.get('location', ''),
                product_requirements=sol_details.get('product_requirements', ''),
                analysis_summary='',
                data=str(sol_details)
            )
            
            # Check if it's a product solicitation
            title_lower = sol_details.get('title', '').lower()
            desc_lower = sol_details.get('description', '').lower()
            
            if any(word in title_lower or word in desc_lower for word in ['product', 'equipment', 'supplies', 'parts']):
                product_sol = sol_details
                print(f"\n✅ Selected PRODUCT solicitation:")
                print(f"   Contract ID: {product_sol['contract_id']}")
                print(f"   Title: {product_sol['title'][:80]}...")
                break
    
    if not product_sol:
        print("❌ No product solicitations found in this batch")
        print("💡 Try running the test again or changing the search keyword")
        return False
    
    contract_id = product_sol['contract_id']
    
    print(f"\n📊 Check dashboard > Solicitations to see this entry!")
    wait_for_user()
    
    # ========================================================================
    # STEP 2: Generate RFQ
    # ========================================================================
    print_banner("STEP 2: Generating RFQ Document")
    print(f"Contract ID: {contract_id}")
    
    # Download attachments if any
    if product_sol.get('attachments'):
        print(f"\nDownloading {len(product_sol['attachments'])} attachments...")
        scraper.download_attachments(product_sol['attachments'], contract_id)
    
    # Generate RFQ
    print("\n🤖 Generating RFQ with AI (this may take 1-2 minutes)...")
    
    result = reader.create_summary_report(
        notice_id=contract_id,
        skip_json=True,
        strict_fidelity=True,
        enable_self_healing=True,
        max_healing_iterations=3
    )
    
    if not result.get('success'):
        print(f"❌ RFQ generation failed: {result.get('error')}")
        return False
    
    print(f"\n✅ RFQ generated successfully!")
    print(f"   Quality Score: {result.get('quality_score', 'N/A')}/100")
    
    # Find the generated .docx file
    rfq_pattern = f"rfq_downloads/2*/{contract_id}_RFQ_*.docx"
    rfq_files = glob.glob(rfq_pattern)
    
    if not rfq_files:
        print("❌ RFQ .docx file not found!")
        return False
    
    rfq_file_path = rfq_files[0]
    print(f"   File: {rfq_file_path}")
    print(f"   Size: {os.path.getsize(rfq_file_path):,} bytes")
    
    print(f"\n📊 Check dashboard > RFQs to see this entry!")
    wait_for_user()
    
    # ========================================================================
    # STEP 3: Submit to ThomasNet
    # ========================================================================
    print_banner("STEP 3: Submitting to ThomasNet Vendors")
    
    # Extract product name from RFQ or solicitation
    product_name = product_sol.get('title', 'Industrial Equipment')
    if len(product_name) > 50:
        product_name = ' '.join(product_name.split()[:5])
    
    print(f"Product: {product_name}")
    print(f"RFQ File: {os.path.basename(rfq_file_path)}")
    print(f"Max Vendors: 5")
    
    print("\n⚠️  IMPORTANT:")
    print("   1. Chrome must be running with remote debugging (port 9222)")
    print("   2. You must be signed in to ThomasNet")
    print("   3. You'll see the browser automation in action")
    
    wait_for_user("\n🌐 Ready to submit to ThomasNet? Press ENTER...")
    
    # Prepare product data
    product_data = {
        'contract_id': contract_id,
        'notice_id': contract_id,
        'product_name': product_name,
        'quantity': 'See attached RFQ',
        'due_date': 'ASAP'
    }
    
    # Submit
    print("\n🚀 Starting ThomasNet submission...")
    thomasnet_result = thomasnet.select_vendors_and_submit_rfq(
        product=product_data,
        limit=5,
        attachment_file_path=rfq_file_path
    )
    
    # Results
    print("\n" + "="*80)
    if thomasnet_result.get('success'):
        print("✅ THOMASNET SUBMISSION SUCCESSFUL!")
        print(f"   Vendors Contacted: {thomasnet_result['vendors_contacted']}")
        print(f"   Confirmation: {thomasnet_result.get('confirmation_message', 'N/A')}")
    else:
        print("❌ THOMASNET SUBMISSION FAILED")
        print(f"   Error: {thomasnet_result.get('error', 'Unknown')}")
    print("="*80)
    
    print(f"\n📊 Check dashboard > Vendors to see the submissions!")
    
    # ========================================================================
    # STEP 4: Review on Dashboard
    # ========================================================================
    print_banner("STEP 4: Review on Dashboard")
    
    print("🎉 Test Complete! Now review everything on the dashboard:")
    print()
    print("1. Home Page (/):")
    print("   - See updated statistics")
    print("   - Check recent activity")
    print()
    print("2. Solicitations (/solicitations):")
    print(f"   - Search for: {contract_id}")
    print("   - View solicitation details")
    print()
    print("3. RFQs (/rfqs):")
    print(f"   - Find contract: {contract_id}")
    print("   - Download the .docx file")
    print("   - Try regenerating it (optional)")
    print()
    print("4. Vendors (/vendors):")
    print(f"   - See {thomasnet_result.get('vendors_contacted', 0)} submissions")
    print(f"   - Product: {product_name}")
    print("   - Try grouping by product")
    print()
    print("5. Automation (/automation):")
    print("   - Check automation status")
    print("   - View recent logs")
    print()
    
    print("\n" + "="*80)
    print(" 🎊 END-TO-END TEST COMPLETE!")
    print("="*80)
    print(f"\nDashboard: http://localhost:5000")
    print(f"Contract ID: {contract_id}")
    print()
    
    return True

if __name__ == "__main__":
    print("\n" + "🔬 COMPREHENSIVE END-TO-END TEST" + "\n")
    print("Prerequisites:")
    print("  ✓ Dashboard running on http://localhost:5000")
    print("  ✓ Chrome with remote debugging on port 9222")
    print("  ✓ Signed in to ThomasNet")
    print()
    
    try:
        success = test_complete_workflow()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
