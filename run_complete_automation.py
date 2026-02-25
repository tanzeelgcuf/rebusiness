#!/usr/bin/env python3
"""
Fully Automated End-to-End Workflow:
sam.gov RFQ Generation → ThomasNet Vendor Submission with Attachments

This script continuously:
1. Generates RFQs from sam.gov → saves as .docx
2. Extracts product names from the RFQ documents
3. Searches ThomasNet for vendors
4. Selects top vendors and submits RFQ with attachment

Usage:
    # Continuous mode (monitors and processes new RFQs)
    python3 run_complete_automation.py --continuous
    
    # Process a single RFQ file
    python3 run_complete_automation.py --rfq rfq_downloads/2026-01-22/abc123_RFQ_PRODUCT.docx
    
    # Run main workflow to generate RFQs, then submit to ThomasNet
    python3 run_complete_automation.py --generate-and-submit --keyword "industrial bolts"
"""

import os
import sys
import time
import glob
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Import agents
from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent
from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager


def extract_product_name_from_docx(docx_path):
    """
    Extract product/service name from RFQ .docx file.
    
    Strategy:
    1. Try to extract from filename (contract_id)
    2. Parse the .docx and look for title/product sections
    3. Fallback to a generic term
    
    Returns:
        str: Product name for ThomasNet search
    """
    try:
        # Method 1: Extract from database using contract_id
        filename = os.path.basename(docx_path)
        contract_id = filename.split('_RFQ_')[0]
        
        db = DatabaseManager()
        solicitation = db.get_solicitation_by_id(contract_id)
        
        if solicitation and solicitation.get('title'):
            title = solicitation['title']
            logger.info(f"  Product name from DB: {title}")
            
            # Clean and shorten for search
            # Remove common government terms
            clean_title = title.replace('SOLICITATION', '').replace('RFQ', '')
            clean_title = clean_title.replace('Request for Quote', '').strip()
            
            # Take first meaningful part (usually the product)
            words = clean_title.split()
            if len(words) > 5:
                product_name = ' '.join(words[:5])
            else:
                product_name = clean_title
                
            return product_name
        
        # Method 2: Parse .docx (requires python-docx)
        try:
            from docx import Document
            doc = Document(docx_path)
            
            # Look for title in first few paragraphs
            for i, para in enumerate(doc.paragraphs[:10]):
                text = para.text.strip()
                if i == 0 and text:  # First paragraph often has title
                    return text[:100]  # Limit length
                    
        except Exception as e:
            logger.warning(f"  Could not parse .docx: {e}")
        
        # Method 3: Fallback to filename-based guess
        logger.warning(f"  Using fallback product name extraction")
        return "Industrial Equipment"
        
    except Exception as e:
        logger.error(f"  Error extracting product name: {e}")
        return "Product"


def process_rfq_file(rfq_path, thomasnet_agent, max_vendors=5):
    """
    Process a single RFQ file:
    1. Extract product name
    2. Submit to ThomasNet vendors with attachment
    
    Args:
        rfq_path: Path to RFQ .docx file
        thomasnet_agent: Initialized ThomasNetAgent
        max_vendors: Number of vendors to contact
    
    Returns:
        dict: Result with success status
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Processing RFQ: {rfq_path}")
    logger.info(f"{'='*80}")
    
    if not os.path.exists(rfq_path):
        logger.error(f"RFQ file not found: {rfq_path}")
        return {'success': False, 'error': 'File not found'}
    
    # Extract product name
    logger.info("Step 1: Extracting product name from RFQ...")
    product_name = extract_product_name_from_docx(rfq_path)
    logger.info(f"  Product: {product_name}")
    
    # Prepare product data
    product = {
        'product_name': product_name,
        'quantity': 'See attached RFQ',
        'due_date': 'ASAP'
    }
    
    # Submit to ThomasNet
    logger.info(f"\nStep 2: Submitting to ThomasNet...")
    logger.info(f"  Product: {product_name}")
    logger.info(f"  Attachment: {os.path.basename(rfq_path)}")
    logger.info(f"  Max vendors: {max_vendors}")
    
    result = thomasnet_agent.select_vendors_and_submit_rfq(
        product=product,
        limit=max_vendors,
        attachment_file_path=rfq_path
    )
    
    if result.get('success'):
        logger.info(f"\n✅ SUCCESS!")
        logger.info(f"  Vendors contacted: {result['vendors_contacted']}")
        logger.info(f"  RFQ file: {os.path.basename(rfq_path)}")
    else:
        logger.error(f"\n❌ FAILED: {result.get('error')}")
    
    return result


def find_unprocessed_rfqs(rfq_dir="rfq_downloads", processed_log="thomasnet_processed.txt"):
    """
    Find RFQ files that haven't been submitted to ThomasNet yet.
    
    Returns:
        list: Paths to unprocessed .docx files
    """
    # Get all .docx files
    all_rfqs = []
    for date_folder in glob.glob(os.path.join(rfq_dir, "2*")):
        rfqs = glob.glob(os.path.join(date_folder, "*_RFQ_PRODUCT.docx"))
        all_rfqs.extend(rfqs)
    
    # Get processed list
    processed = set()
    if os.path.exists(processed_log):
        with open(processed_log, 'r') as f:
            processed = set(line.strip() for line in f)
    
    # Filter unprocessed
    unprocessed = [rfq for rfq in all_rfqs if rfq not in processed]
    unprocessed.sort(key=os.path.getmtime, reverse=True)  # Most recent first
    
    return unprocessed


def mark_as_processed(rfq_path, processed_log="thomasnet_processed.txt"):
    """Mark an RFQ as processed to avoid resubmission."""
    with open(processed_log, 'a') as f:
        f.write(f"{rfq_path}\n")


def continuous_mode(interval_minutes=180, max_vendors=5):
    """
    Continuously monitor for new RFQs and submit to ThomasNet.
    
    Args:
        interval_minutes: Check interval in minutes (default: 180 = 3 hours)
        max_vendors: Vendors per product
    """
    logger.info("="*80)
    logger.info(" CONTINUOUS AUTOMATION MODE")
    logger.info("="*80)
    logger.info(f"Checking for new RFQs every {interval_minutes} minutes ({interval_minutes/60:.1f} hours)")
    logger.info(f"Max vendors per product: {max_vendors}")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*80)
    
    agent = ThomasNetAgent()
    
    try:
        while True:
            logger.info(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for new RFQs...")
            
            unprocessed = find_unprocessed_rfqs()
            
            if unprocessed:
                logger.info(f"Found {len(unprocessed)} unprocessed RFQ(s)")
                
                for rfq_path in unprocessed:
                    result = process_rfq_file(rfq_path, agent, max_vendors)
                    
                    if result.get('success'):
                        mark_as_processed(rfq_path)
                        logger.info(f"✅ Marked as processed: {rfq_path}")
                    else:
                        logger.warning(f"⚠️  Failed to process: {rfq_path}")
                        # Don't mark as processed so it can be retried
            else:
                logger.info("No new RFQs found")
            
            # Sleep
            logger.info(f"\nSleeping for {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
            
    except KeyboardInterrupt:
        logger.info("\n\nStopping continuous mode...")
    except Exception as e:
        logger.error(f"Error in continuous mode: {e}")


def generate_and_submit_mode(keyword=None, num_pages=10, max_vendors=5):
    """
    Run the full pipeline:
    1. Generate RFQs from sam.gov
    2. Automatically submit to ThomasNet
    
    Args:
        keyword: Search keyword for sam.gov
        num_pages: Pages to scrape
        max_vendors: Vendors per product
    """
    logger.info("="*80)
    logger.info(" GENERATE & SUBMIT MODE")
    logger.info("="*80)
    logger.info(f"Keyword: {keyword or 'batch rotation'}")
    logger.info(f"Pages: {num_pages}")
    logger.info(f"Max vendors: {max_vendors}")
    logger.info("="*80)
    
    # Import main workflow
    from main_workflow import main_job
    import argparse
    
    # Create args for main_workflow
    args = argparse.Namespace()
    args.submit_to_thomasnet = False  # We'll handle it ourselves
    args.strict_fidelity = True
    args.template_type = "auto-detect"
    args.internal_deadline_offset = 4
    args.vendor_email = "john@campsable.com"
    args.organization_name = "Camp Sable, LLC"
    args.no_self_healing = False
    args.max_healing_iterations = 3
    
    # Track RFQs before generation
    rfqs_before = set(glob.glob("rfq_downloads/2*/*_RFQ_PRODUCT.docx"))
    
    # Generate RFQs
    logger.info("\nStep 1: Generating RFQs from sam.gov...")
    main_job(target_keyword=keyword, force_num_pages=num_pages, args=args)
    
    # Find new RFQs
    rfqs_after = set(glob.glob("rfq_downloads/2*/*_RFQ_PRODUCT.docx"))
    new_rfqs = list(rfqs_after - rfqs_before)
    
    if not new_rfqs:
        logger.warning("\nNo new RFQs generated")
        return
    
    logger.info(f"\n✅ Generated {len(new_rfqs)} new RFQ(s)")
    
    # Submit to ThomasNet
    logger.info("\nStep 2: Submitting to ThomasNet...")
    agent = ThomasNetAgent()
    
    for rfq_path in new_rfqs:
        result = process_rfq_file(rfq_path, agent, max_vendors)
        
        if result.get('success'):
            mark_as_processed(rfq_path)
        
        # Small delay between submissions
        time.sleep(5)
    
    logger.info("\n" + "="*80)
    logger.info(" COMPLETE!")
    logger.info("="*80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Complete sam.gov → ThomasNet Automation Pipeline"
    )
    parser.add_argument(
        "--mode",
        choices=['continuous', 'single', 'generate-and-submit'],
        default='single',
        help="Automation mode"
    )
    parser.add_argument(
        "--rfq",
        type=str,
        help="Path to single RFQ file to process"
    )
    parser.add_argument(
        "--continuous",
        action='store_true',
        help="Continuous monitoring mode"
    )
    parser.add_argument(
        "--generate-and-submit",
        action='store_true',
        help="Generate RFQs then submit to ThomasNet"
    )
    parser.add_argument(
        "--keyword",
        type=str,
        help="Search keyword for sam.gov (for generate mode)"
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=10,
        help="Pages to scrape (for generate mode)"
    )
    parser.add_argument(
        "--max-vendors",
        type=int,
        default=5,
        help="Maximum vendors to contact per product"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=180,
        help="Check interval in minutes (for continuous mode, default: 180 = 3 hours)"
    )
    
    args = parser.parse_args()
    
    # Determine mode
    if args.continuous or args.mode == 'continuous':
        continuous_mode(interval_minutes=args.interval, max_vendors=args.max_vendors)
    
    elif args.generate_and_submit or args.mode == 'generate-and-submit':
        generate_and_submit_mode(
            keyword=args.keyword,
            num_pages=args.pages,
            max_vendors=args.max_vendors
        )
    
    elif args.rfq:
        # Single RFQ mode
        agent = ThomasNetAgent()
        result = process_rfq_file(args.rfq, agent, max_vendors=args.max_vendors)
        sys.exit(0 if result.get('success') else 1)
    
    else:
        # Default: Process all unprocessed RFQs once
        logger.info("Processing all unprocessed RFQs...")
        unprocessed = find_unprocessed_rfqs()
        
        if not unprocessed:
            logger.info("No unprocessed RFQs found")
            sys.exit(0)
        
        logger.info(f"Found {len(unprocessed)} unprocessed RFQ(s)")
        agent = ThomasNetAgent()
        
        for rfq_path in unprocessed:
            result = process_rfq_file(rfq_path, agent, max_vendors=args.max_vendors)
            if result.get('success'):
                mark_as_processed(rfq_path)
