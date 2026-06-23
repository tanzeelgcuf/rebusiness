#!/usr/bin/env python3
"""
RFQ Submission wrapper that uses the dashboard's browser connector
to submit RFQs to ThomasNet using an existing authenticated session.

This bypasses the CLI's browser startup issues and leverages the
dashboard's proven connection method.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dashboard.utils.browser_connector import connect_to_browser
from ai_agents.ThomasNetAgent.rfq_parser import RFQParser
from ai_agents.ThomasNetAgent.searcher import ThomasNetSearch
from ai_agents.ThomasNetAgent.vendor_selector import VendorSelector
from ai_agents.ThomasNetAgent.form_filler import RFQFormFiller
import logging
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def submit_rfq(rfq_path: str, max_vendors: int = 5, dry_run: bool = False):
    """
    Submit an RFQ to ThomasNet using dashboard's browser connection

    Args:
        rfq_path: Path to RFQ file (markdown, PDF, or DOCX)
        max_vendors: Maximum number of vendors to submit to
        dry_run: If True, just parse and display without submitting
    """

    console.print(f"\n[bold blue]🚀 ThomasNet RFQ Submission (Dashboard Method)[/bold blue]")
    console.print(f"RFQ File: {rfq_path}\n")

    # Step 1: Parse RFQ
    console.print("[yellow]📄 Step 1: Parsing RFQ document...[/yellow]")
    try:
        parser = RFQParser()
        rfq_data = parser.parse_file(rfq_path)

        if not rfq_data.get('products'):
            console.print("[red]❌ No products found in RFQ[/red]")
            return False

        console.print(f"✅ Found {len(rfq_data['products'])} product(s)")
        for i, product in enumerate(rfq_data['products'][:3], 1):
            console.print(f"   {i}. {product.get('name', 'Unknown')}")

    except Exception as e:
        console.print(f"[red]❌ Failed to parse RFQ: {e}[/red]")
        return False

    if dry_run:
        console.print("\n[yellow]📋 DRY RUN MODE - Parsing complete, skipping submission[/yellow]")
        return True

    # Step 2: Connect to browser
    console.print("\n[yellow]🌐 Step 2: Connecting to browser...[/yellow]")
    try:
        browser, page = connect_to_browser()
        console.print("✅ Browser connected")
    except Exception as e:
        console.print(f"[red]❌ Failed to connect to browser: {e}[/red]")
        return False

    try:
        # Step 3: Search for vendors
        console.print(f"\n[yellow]🔍 Step 3: Searching for {max_vendors} vendors...[/yellow]")

        searcher = ThomasNetSearch(page)

        # Search for first product
        first_product = rfq_data['products'][0]
        search_query = first_product.get('name', '')

        if not search_query:
            console.print("[red]❌ No product name to search for[/red]")
            return False

        console.print(f"   Searching: {search_query}")
        vendors = searcher.search_suppliers(search_query, max_results=max_vendors)

        console.print(f"✅ Found {len(vendors)} vendors")
        for i, vendor in enumerate(vendors[:3], 1):
            console.print(f"   {i}. {vendor.get('name', 'Unknown')} - {vendor.get('url', 'N/A')}")

        # Step 4: Submit to vendors
        console.print(f"\n[yellow]📤 Step 4: Submitting RFQ to vendors...[/yellow]")

        form_filler = RFQFormFiller(page)
        submitted_count = 0

        for i, vendor in enumerate(vendors[:max_vendors], 1):
            try:
                console.print(f"   [{i}/{len(vendors[:max_vendors])}] {vendor.get('name', 'Vendor')}...", end=" ")

                # Navigate to vendor contact form
                vendor_url = vendor.get('contact_url') or vendor.get('url')
                if vendor_url:
                    page.goto(vendor_url, wait_until='networkidle', timeout=30000)

                    # Fill form with RFQ data
                    form_filler.fill_vendor_form(rfq_data, vendor)

                    console.print("✅")
                    submitted_count += 1
                else:
                    console.print("⚠️  (no contact URL)")

            except Exception as e:
                console.print(f"❌ ({str(e)[:30]})")
                continue

        console.print(f"\n✅ Submitted to {submitted_count}/{len(vendors[:max_vendors])} vendors")
        return True

    except Exception as e:
        console.print(f"[red]❌ Submission error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if page:
            page.close()

if __name__ == '__main__':
    import click

    @click.command()
    @click.option('--rfq', required=True, help='Path to RFQ file')
    @click.option('--max-vendors', default=5, type=int, help='Max vendors to submit to')
    @click.option('--dry-run', is_flag=True, help='Parse only, do not submit')
    def cli(rfq, max_vendors, dry_run):
        """Submit RFQ to ThomasNet vendors using dashboard browser connection"""
        success = submit_rfq(rfq, max_vendors=max_vendors, dry_run=dry_run)
        sys.exit(0 if success else 1)

    cli()
