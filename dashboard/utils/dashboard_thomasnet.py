#!/usr/bin/env python3
"""
Dashboard ThomasNet Automation
Processes and submits RFQs to ThomasNet using an existing logged-in browser session
to avoid IP blocking.
"""

import os
import sys
import glob
import logging
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
current_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(current_dir))

from dashboard.utils.browser_connector import connect_to_browser
from ai_agents.ThomasNetAgent.searcher import ThomasNetSearch
from ai_agents.ThomasNetAgent.vendor_selector import VendorSelector
from ai_agents.ThomasNetAgent.form_filler import RFQFormFiller

logger = logging.getLogger(__name__)

from database_manager import DatabaseManager

# Initialize DB
db = DatabaseManager()

def find_unprocessed_rfqs() -> List[str]:
    """
    Find RFQ files that haven't been submitted to ThomasNet
    
    Returns:
        List of file paths to unprocessed RFQs
    """
    # Find all RFQ files
    pattern = os.path.join(current_dir, "rfq_downloads/2*/*_RFQ_PRODUCT.docx")
    all_rfqs = glob.glob(pattern)
    
    # 1. Check DB for already sent RFQs
    sent_rfqs = db.get_all_rfqs(limit=1000, sent_status='sent')
    sent_contract_ids = {r['contract_id'] for r in sent_rfqs}
    
    # 2. Also check legacy text file for safety
    processed_file = os.path.join(current_dir, 'thomasnet_processed.txt')
    processed_paths = set()
    if os.path.exists(processed_file):
        with open(processed_file, 'r') as f:
            processed_paths = set(line.strip() for line in f if line.strip())
            
    unprocessed = []
    for rfq_path in all_rfqs:
        # Extract contract_id from filename (e.g., "id_RFQ_PRODUCT.docx")
        filename = os.path.basename(rfq_path)
        contract_id = filename.split('_')[0]
        
        # Check if sent in DB OR in text file
        if contract_id in sent_contract_ids or os.path.abspath(rfq_path) in processed_paths:
            continue
            
        unprocessed.append(rfq_path)
    
    processed_count = len(all_rfqs) - len(unprocessed)
    if processed_count > 0:
        logger.info(f"♻️  Skipping {processed_count} already processed RFQs")
    
    logger.info(f"Found {len(unprocessed)} unprocessed RFQs (out of {len(all_rfqs)} total)")
    return unprocessed

def mark_as_processed(rfq_path: str):
    """Mark an RFQ as processed in DB and text file"""
    # 1. Update DB
    filename = os.path.basename(rfq_path)
    contract_id = filename.split('_')[0]
    # We only have email if we extracted it, but for now mark as sent without specific email
    db.mark_rfq_sent(contract_id, "thomasnet_batch_submission")
    
    # 2. Update text file (legacy backup)
    processed_file = os.path.join(current_dir, 'thomasnet_processed.txt')
    with open(processed_file, 'a') as f:
        f.write(f"{os.path.abspath(rfq_path)}\n")
    logger.info(f"Marked as processed: {filename}")

def extract_product_name(rfq_path: str) -> str:
    """
    Extract product name from RFQ document
    
    Args:
        rfq_path: Path to RFQ .docx file
        
    Returns:
        Product name string
    """
    # If it's a PDF or MD, we use a simpler approach or the filename
    filename = os.path.basename(rfq_path).lower()
    
    if filename.endswith('.md') or filename.endswith('.txt'):
        try:
            with open(rfq_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Look for "Item Requested:" or "Product:" or "Subject:"
                import re
                patterns = [
                    r'Item Requested:\s*(.*)',
                    r'Product:\s*(.*)',
                    r'Subject:\s*(.*)',
                    r'Notice ID:.*\n\s*(.*)'
                ]
                for pattern in patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        product = match.group(1).strip()
                        if product and len(product) > 3 and not any(skip in product.lower() for skip in ['general information', 'scope']):
                             logger.info(f"✓ Extracted product from {filename}: '{product}'")
                             return product
        except:
             pass
    
    # Filename fallback: try to extract product name from "contractid_RFQ_PRODUCT.docx"
    try:
        if '_RFQ_' in filename:
            product = filename.split('_RFQ_')[1].split('.')[0]
            if product:
                return product.replace('_', ' ')
    except:
        pass

    if not filename.endswith('.docx'):
        logger.warning(f"File is not .docx, using generic product name for {filename}")
        return "Industrial Product"

    try:
        from docx import Document
        doc = Document(rfq_path)
        
        # Method 1: Look for "Item Requested:" field (most reliable)
        for para in doc.paragraphs[:60]:  # Search first 60 paragraphs
            text = para.text.strip()
            # Case-insensitive check and more flexible match
            if 'item requested' in text.lower():
                # Extract the text after "Item Requested" or "Item Requested:"
                import re
                match = re.search(r'item requested:?\s*(.*)', text, re.IGNORECASE)
                if match:
                    product = match.group(1).strip()
                    if product:
                        logger.info(f"✓ Extracted product from 'Item Requested:': '{product}'")
                        return product
        
        # Method 2: Product name is typically the line RIGHT AFTER "Notice ID:\" line
        for i, para in enumerate(doc.paragraphs[:20]):
            text = para.text.strip()
            if 'notice id' in text.lower():
                # Get the next non-empty paragraph
                for j in range(i+1, min(i+8, len(doc.paragraphs))):
                    next_text = doc.paragraphs[j].text.strip()
                    if next_text and len(next_text) > 3:
                        # This should be the product name
                        # Skip if it's a common header/greeting
                        if not any(skip in next_text.lower() for skip in 
                                 ['dear vendor', 'we are writing', 'your response', 'general information']):
                            logger.info(f"✓ Extracted product (from title): '{next_text}'")
                            return next_text
        
        # Fallback: Look for first meaningful paragraph
        for para in doc.paragraphs[:15]:
            text = para.text.strip()
            # Check for reasonable product name length and avoids short section headers
            if text and 10 < len(text) < 150:
                text_lower = text.lower()
                skip_list = [
                    'request for quotation', 'rfq', 'date:', 'contract', 
                    'camp sable', 'dear vendor', 'notice id', 'we are writing',
                    'general information', 'scope of work', 'background',
                    'requirements', 'specifications', 'instructions', 'terms and conditions'
                ]
                if not any(skip in text_lower for skip in skip_list):
                    logger.info(f"✓ Extracted product (fallback): '{text}'")
                    return text
        
        # Last resort: use a generic name
        logger.warning(f"Could not extract product name from {os.path.basename(rfq_path)}, using fallback")
        return "Industrial Product"
        
    except Exception as e:
        logger.error(f"Error extracting product name: {e}")
        return "Product"


def submit_rfq_to_vendors(page, rfq_path: str, max_vendors: int = 5) -> Dict:
    """
    Submit a single RFQ to ThomasNet vendors
    
    Args:
        page: Playwright page object (already connected to logged-in session)
        rfq_path: Path to RFQ document
        max_vendors: Maximum number of vendors to contact
        
    Returns:
        Dictionary with submission results
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Processing RFQ: {os.path.basename(rfq_path)}")
    logger.info(f"{'='*80}")

    # Slider verification check before starting
    slider_solved = None
    try:
        from ai_agents.ThomasNetAgent.captcha_solver import detect_datadome
        if detect_datadome(page):
            logger.info("⚠️  DataDome slider detected — attempting automated solve...")
            from ai_agents.ThomasNetAgent.form_filler import solve_slider_if_present
            slider_solved = solve_slider_if_present(page)
            if slider_solved:
                logger.info("✅ DataDome slider solved successfully before submission")
            else:
                logger.warning("❌ DataDome slider NOT solved — submission may fail")
        else:
            logger.info("✅ No DataDome slider detected — proceeding")
            slider_solved = True
    except Exception as e:
        logger.warning(f"Slider check skipped: {e}")
    
    try:
        # Extract product name
        product_name = extract_product_name(rfq_path)
        logger.info(f"Product: {product_name}")
        
        # Navigate to homepage to ensure clean state
        logger.info("Navigating to homepage to reset state...")
        try:
            page.goto("https://www.thomasnet.com", wait_until="domcontentloaded", timeout=30000)
            import time
            time.sleep(3)
        except Exception as e:
            logger.warning(f"Error navigating to homepage: {e}")

        # Search for vendors
        logger.info(f"Searching for vendors...")
        searcher = ThomasNetSearch(page)
        vendors = searcher.search_vendors(product_name, max_results=20)
        
        if not vendors:
            logger.warning("No vendors found")
            return {
                'success': False,
                'error': 'No vendors found',
                'vendors_contacted': 0,
                'slider_solved': slider_solved
            }
        
        logger.info(f"Found {len(vendors)} vendors")
        
        # Select top vendors
        selector = VendorSelector()
        selected_vendors = selector.select_top_vendors(vendors, {'product_name': product_name})
        logger.info(f"Selected {len(selected_vendors)} vendors for submission (max {max_vendors})")
        
        # Get vendor names for batch submission
        vendor_names = [v.get('name') for v in selected_vendors[:max_vendors]]
        
        if not vendor_names:
            logger.warning("No vendor names extracted")
            return {
                'success': False,
                'error': 'No valid vendors to contact',
                'vendors_contacted': 0,
                'slider_solved': slider_solved
            }
        
        # Submit RFQs using multi-vendor batch system
        filler = RFQFormFiller(page)
        
        # Prepare RFQ summary (truncated to 100 chars)
        rfq_summary = f"Request for quotation for {product_name}. Please review attached RFQ document."[:100]
        
        logger.info(f"\nSubmitting batch RFQ to {len(vendor_names)} vendors...")
        
        result = filler.submit_multi_vendor_rfq(
            product_name=product_name,
            vendors=vendor_names,
            summary=rfq_summary,
            rfq_file_path=rfq_path
        )
        
        if result.get('success'):
            logger.info(f"\n{'='*80}")
            logger.info(f"✅ Completed: {result['vendors_contacted']} vendors contacted")
            logger.info(f"{'='*80}\n")
        else:
            logger.error(f"\n{'='*80}")
            logger.error(f"❌ Failed: {result.get('error')}")
            logger.error(f"{'='*80}\n")

        result['slider_solved'] = slider_solved
        return result
        
    except Exception as e:
        logger.error(f"Error processing RFQ: {e}")
        return {
            'success': False,
            'error': str(e),
            'vendors_contacted': 0,
            'slider_solved': slider_solved
        }

def run_dashboard_thomasnet_submission(max_vendors: int = 5, cdp_url: str = "http://127.0.0.1:9222") -> Dict:
    """
    Main function to run ThomasNet submissions from dashboard
    
    Args:
        max_vendors: Maximum vendors per RFQ
        cdp_url: Chrome DevTools Protocol URL
        
    Returns:
        Dictionary with overall results
    """
    logger.info("\n" + "="*80)
    logger.info("DASHBOARD THOMASNET SUBMISSION")
    logger.info("="*80)
    
    try:
        # Connect to browser
        logger.info("Connecting to browser...")
        print("DEBUG: Connecting to browser via connect_to_browser...")
        browser, page, connector = connect_to_browser(cdp_url, validate_login=True)
        print("DEBUG: Browser connected successfully.")
        
        # Find unprocessed RFQs
        unprocessed = find_unprocessed_rfqs()
        
        if not unprocessed:
            logger.info("No unprocessed RFQs found")
            connector.close()
            return {
                'success': True,
                'rfqs_processed': 0,
                'vendors_contacted': 0,
                'message': 'No pending RFQs to process'
            }
        
        logger.info(f"\nProcessing {len(unprocessed)} RFQ(s)...\n")
        
        # Process each RFQ
        total_vendors_contacted = 0
        rfqs_processed = 0
        
        for rfq_path in unprocessed:
            print(f"DEBUG: Processing RFQ: {rfq_path}")
            result = submit_rfq_to_vendors(page, rfq_path, max_vendors)
            
            if result.get('success'):
                mark_as_processed(rfq_path)
                rfqs_processed += 1
                total_vendors_contacted += result.get('vendors_contacted', 0)
            
            # Small delay between RFQs
            import time
            time.sleep(2)
        
        # Close connection
        connector.close()
        
        logger.info("\n" + "="*80)
        logger.info("SUBMISSION COMPLETE")
        logger.info(f"RFQs processed: {rfqs_processed}/{len(unprocessed)}")
        logger.info(f"Vendors contacted: {total_vendors_contacted}")
        logger.info("="*80 + "\n")
        
        return {
            'success': True,
            'rfqs_processed': rfqs_processed,
            'vendors_contacted': total_vendors_contacted,
            'message': f'Processed {rfqs_processed} RFQs, contacted {total_vendors_contacted} vendors'
        }
        
    except Exception as e:
        logger.error(f"Submission failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'rfqs_processed': 0,
            'vendors_contacted': 0
        }


def submit_single_rfq_task(rfq_path: str, max_vendors: int = 5, cdp_url: str = "http://127.0.0.1:9222"):
    """
    Run submission for a single RFQ task (intended for background threads)
    """
    # Wire ALL loggers to write to submission.log for full visibility
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'submission.log')

    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))

    # Attach to root so browser_connector, searcher, form_filler all write here
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)

    logger.info(f"=== SINGLE RFQ SUBMISSION: {os.path.basename(rfq_path)} ===")

    conn = None
    try:
        logger.info("Connecting to browser (headless via auth_state.json)...")
        browser, page, conn = connect_to_browser(cdp_url, validate_login=True)
        logger.info("Browser connected successfully.")

        logger.info("Calling submit_rfq_to_vendors...")
        result = submit_rfq_to_vendors(page, rfq_path, max_vendors)
        logger.info(f"Result: {result}")

        # Log slider status
        slider = result.get('slider_solved')
        if slider is True:
            logger.info("✅ DataDome slider: Solved")
        elif slider is False:
            logger.warning("❌ DataDome slider: NOT solved")
        else:
            logger.info("⚪ DataDome slider: Not checked")

        if result.get('success'):
            mark_as_processed(rfq_path)
            logger.info(f"✅ Submission successful: {result.get('vendors_contacted', 0)} vendors contacted")
        else:
            logger.error(f"❌ Submission failed: {result.get('error')}")

    except Exception as e:
        logger.error(f"Single submission error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if conn:
            logger.info("Closing browser connection.")
            conn.close()
        root_logger.removeHandler(file_handler)
        file_handler.close()


if __name__ == "__main__":
    """Test the dashboard automation"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    import argparse
    parser = argparse.ArgumentParser(description="Dashboard ThomasNet Automation")
    parser.add_argument('--test-one', action='store_true', help='Test with one RFQ only')
    parser.add_argument('--max-vendors', type=int, default=5, help='Max vendors per RFQ')
    args = parser.parse_args()
    
    if args.test_one:
        # Test with one RFQ
        unprocessed = find_unprocessed_rfqs()
        if unprocessed:
            logger.info(f"Testing with: {unprocessed[0]}")
            try:
                browser, page, connector = connect_to_browser(validate_login=True)
                result = submit_rfq_to_vendors(page, unprocessed[0], max_vendors=args.max_vendors)
                connector.close()
                print(f"\nResult: {result}")
            except Exception as e:
                logger.error(f"Test failed: {e}")
        else:
            logger.info("No unprocessed RFQs found for testing")
    else:
        # Run full automation
        result = run_dashboard_thomasnet_submission(max_vendors=args.max_vendors)
        print(f"\nFinal result: {result}")
