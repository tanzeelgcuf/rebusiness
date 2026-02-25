#!/usr/bin/env python3
"""
Complete ThomasNet Automation Script
Combines all modules for end-to-end RFQ submission workflow
"""
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_agents.ThomasNetAgent.searcher import ThomasNetSearch
from ai_agents.ThomasNetAgent.vendor_selector import VendorSelector
from ai_agents.ThomasNetAgent.form_filler import RFQFormFiller

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/automation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ThomasNetAutomation:
    """Complete automation workflow for ThomasNet RFQ submissions"""
    
    def __init__(self, headless=False, use_proxy=False):
        self.headless = headless
        self.use_proxy = use_proxy
        self.browser = None
        self.context = None
        self.page = None
        self.results = []
        
    def setup_browser(self, playwright):
        """Initialize browser with configuration"""
        logger.info("Setting up browser...")
        
        # Proxy configuration (if enabled)
        proxy_config = None
        if self.use_proxy:
            # Load proxy from .env
            from dotenv import load_dotenv
            import os
            load_dotenv()
            
            proxy_url = os.getenv('THOMASNET_PROXY')
            if proxy_url:
                proxy_config = {"server": proxy_url}
                logger.info(f"Using proxy: {proxy_url}")
        
        # Launch Firefox
        self.browser = playwright.firefox.launch(
            headless=self.headless,
            proxy=proxy_config
        )
        
        self.context = self.browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        
        self.page = self.context.new_page()
        logger.info("Browser setup complete")
        
    def login(self):
        """Navigate to ThomasNet and wait for manual login"""
        logger.info("Navigating to ThomasNet...")
        self.page.goto("https://www.thomasnet.com")
        
        print()
        print("=" * 70)
        print("MANUAL LOGIN REQUIRED")
        print("=" * 70)
        print("1. Log in to ThomasNet in the browser window")
        print("2. Solve any captchas")
        print("3. Come back here and press Enter")
        print("=" * 70)
        print()
        input("Press Enter after you've logged in...")
        print()
        
        logger.info("Login completed")
        
    def search_vendors(self, product_query, max_results=20):
        """Search for vendors matching the product query"""
        logger.info(f"Searching for vendors: {product_query}")
        
        searcher = ThomasNetSearch(self.page)
        vendors = searcher.search_vendors(product_query, max_results=max_results)
        
        logger.info(f"Found {len(vendors)} vendors")
        return vendors
        
    def select_top_vendors(self, vendors, product_name, max_vendors=5):
        """Select top vendors based on ranking criteria"""
        logger.info(f"Selecting top {max_vendors} vendors...")
        
        selector = VendorSelector()
        selected = selector.select_top_vendors(
            vendors,
            product_data={"product_name": product_name}
        )
        
        logger.info(f"Selected {len(selected)} vendors")
        return selected
        
    def submit_rfqs(self, vendors, rfq_summary, dry_run=True):
        """Submit RFQs to selected vendors"""
        logger.info(f"Submitting RFQs to {len(vendors)} vendors (dry_run={dry_run})...")
        
        form_filler = RFQFormFiller(self.page)
        results = []
        
        for i, vendor in enumerate(vendors, 1):
            logger.info(f"Processing vendor {i}/{len(vendors)}: {vendor['name']}")
            
            try:
                if dry_run:
                    # Dry run: just navigate and check form
                    logger.info(f"  Navigating to: {vendor.get('profile_url', 'N/A')}")
                    if vendor.get('profile_url'):
                        self.page.goto(vendor['profile_url'])
                        time.sleep(2)
                        
                        # Check if RFQ button exists
                        rfq_button_found = False
                        rfq_selectors = [
                            'a:has-text("Request Quote")',
                            'button:has-text("Request Quote")',
                            'a:has-text("Contact Supplier")'
                        ]
                        
                        for selector in rfq_selectors:
                            try:
                                if self.page.locator(selector).first.is_visible(timeout=2000):
                                    rfq_button_found = True
                                    logger.info(f"  ✓ Found RFQ button")
                                    break
                            except:
                                continue
                        
                        if not rfq_button_found:
                            logger.warning(f"  ⚠️  No RFQ button found on {vendor['name']}")
                        
                        result = {
                            'success': True,
                            'vendor_name': vendor['name'],
                            'dry_run': True,
                            'rfq_button_found': rfq_button_found
                        }
                    else:
                        result = {
                            'success': False,
                            'vendor_name': vendor['name'],
                            'error': 'No profile URL'
                        }
                else:
                    # Real submission
                    result = form_filler.submit_rfq(
                        vendor=vendor,
                        summary=rfq_summary,
                        rfq_file_path=None  # Optional: add file path if needed
                    )
                
                results.append(result)
                logger.info(f"  Result: {result.get('success', False)}")
                
                # Add delay between submissions (human-like behavior)
                if i < len(vendors):
                    delay = 3 if dry_run else 10
                    logger.info(f"  Waiting {delay}s before next vendor...")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"  Error processing {vendor['name']}: {e}")
                results.append({
                    'success': False,
                    'vendor_name': vendor['name'],
                    'error': str(e)
                })
        
        return results
        
    def generate_report(self, product_name, vendors, submission_results):
        """Generate summary report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'product': product_name,
            'total_vendors_found': len(vendors),
            'vendors_selected': len(submission_results),
            'successful_submissions': sum(1 for r in submission_results if r.get('success')),
            'failed_submissions': sum(1 for r in submission_results if not r.get('success')),
            'results': submission_results
        }
        
        # Save to file
        report_dir = Path('reports')
        report_dir.mkdir(exist_ok=True)
        
        report_file = report_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved to: {report_file}")
        return report
        
    def cleanup(self):
        """Close browser and cleanup"""
        if self.browser:
            self.browser.close()
            logger.info("Browser closed")
            
    def run(self, product_name, rfq_summary, max_vendors=5, dry_run=True):
        """Run complete automation workflow"""
        logger.info("=" * 70)
        logger.info("Starting ThomasNet Automation")
        logger.info("=" * 70)
        logger.info(f"Product: {product_name}")
        logger.info(f"Max vendors: {max_vendors}")
        logger.info(f"Dry run: {dry_run}")
        logger.info("=" * 70)
        
        with sync_playwright() as p:
            try:
                # 1. Setup
                self.setup_browser(p)
                
                # 2. Login
                self.login()
                
                # 3. Search
                vendors = self.search_vendors(product_name, max_results=20)
                
                if not vendors:
                    logger.error("No vendors found. Exiting.")
                    return None
                
                # 4. Select
                selected_vendors = self.select_top_vendors(vendors, product_name, max_vendors)
                
                # 5. Submit RFQs
                results = self.submit_rfqs(selected_vendors, rfq_summary, dry_run=dry_run)
                
                # 6. Generate Report
                report = self.generate_report(product_name, vendors, results)
                
                # 7. Display Summary
                print()
                print("=" * 70)
                print("AUTOMATION COMPLETE")
                print("=" * 70)
                print(f"Product: {product_name}")
                print(f"Vendors found: {len(vendors)}")
                print(f"Vendors selected: {len(selected_vendors)}")
                print(f"Successful: {report['successful_submissions']}")
                print(f"Failed: {report['failed_submissions']}")
                print()
                print("Selected Vendors:")
                for i, vendor in enumerate(selected_vendors, 1):
                    status = "✓" if any(r['vendor_name'] == vendor['name'] and r.get('success') for r in results) else "✗"
                    print(f"  {status} {i}. {vendor['name']} ({vendor.get('location', 'N/A')})")
                print()
                print(f"Report saved to: reports/")
                print("=" * 70)
                
                return report
                
            except Exception as e:
                logger.error(f"Automation failed: {e}")
                import traceback
                traceback.print_exc()
                return None
                
            finally:
                self.cleanup()


def main():
    """Main entry point"""
    print("=" * 70)
    print("ThomasNet Complete Automation")
    print("=" * 70)
    print()
    
    # Configuration
    product_name = "CNC machining services"
    rfq_summary = """Request for Quote: CNC Machining Services

We are seeking quotes for precision CNC machining services for aluminum parts.

Specifications:
- Material: 6061-T6 Aluminum
- Quantity: 100 units
- Tolerance: ±0.005"
- Finish: Anodized

Please provide:
1. Unit price for 100, 500, and 1000 quantities
2. Lead time
3. Quality certifications (ISO 9001, AS9100 if applicable)

Deadline: February 15, 2026

Thank you for your quote."""
    
    # Options
    max_vendors = 5
    dry_run = True  # Set to False for real submissions
    use_proxy = False  # Set to True to use proxy from .env
    
    print(f"Product: {product_name}")
    print(f"Max vendors: {max_vendors}")
    print(f"Dry run: {dry_run}")
    print(f"Use proxy: {use_proxy}")
    print()
    input("Press Enter to start automation...")
    print()
    
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)
    
    # Run automation
    automation = ThomasNetAutomation(headless=False, use_proxy=use_proxy)
    report = automation.run(
        product_name=product_name,
        rfq_summary=rfq_summary,
        max_vendors=max_vendors,
        dry_run=dry_run
    )
    
    if report:
        print()
        print("✓ Automation completed successfully!")
    else:
        print()
        print("✗ Automation failed. Check logs for details.")


if __name__ == "__main__":
    main()
