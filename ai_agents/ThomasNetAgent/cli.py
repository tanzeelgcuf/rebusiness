#!/usr/bin/env python3
"""
ThomasNet RFQ Automation CLI

Usage:
    python cli.py submit --rfq outputs/rfq_product_123.pdf
    python cli.py batch --directory outputs/
    python cli.py test-search "CNC machining"
"""

import click
from rich.console import Console
from rich.table import Table
from rich.progress import track
import yaml
import logging
from pathlib import Path
from datetime import datetime
import json
import sys
import os

# Add parent directory to path to ensure imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ai_agents.ThomasNetAgent.auth import ThomasNetAuth
from ai_agents.ThomasNetAgent.rfq_parser import RFQParser
from ai_agents.ThomasNetAgent.searcher import ThomasNetSearch
from ai_agents.ThomasNetAgent.vendor_selector import VendorSelector
from ai_agents.ThomasNetAgent.summarizer import RFQSummarizer
from ai_agents.ThomasNetAgent.form_filler import RFQFormFiller

console = Console()

# Load configuration
CONFIG_PATH = Path(__file__).parent / "config.yaml"
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r") as f:
        CONFIG = yaml.safe_load(f)
else:
    CONFIG = {}

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'thomasnet_automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@click.group()
def cli():
    """ThomasNet RFQ Automation Tool"""
    pass

@cli.command()
@click.option('--rfq', required=True, type=click.Path(exists=True), help='Path to RFQ file (PDF/DOCX)')
@click.option('--headless/--no-headless', default=None, help='Run browser in headless mode')
@click.option('--max-vendors', default=5, help='Maximum vendors per product')
@click.option('--dry-run', is_flag=True, help='Parse and search only, do not submit')
def submit(rfq, headless, max_vendors, dry_run):
    """Submit RFQ to ThomasNet vendors"""
    
    console.print(f"\n[bold blue]🚀 ThomasNet RFQ Automation[/bold blue]")
    console.print(f"RFQ File: {rfq}\n")
    
    # 1. Parse RFQ document
    console.print("[yellow]📄 Step 1: Parsing RFQ document...[/yellow]")
    parser = RFQParser()
    try:
        rfq_data = parser.parse_file(rfq)
    except Exception as e:
        console.print(f"[red]❌ Failed to parse RFQ: {e}[/red]")
        return
    
    if not rfq_data.get('products'):
        console.print("[red]❌ No products found in RFQ[/red]")
        return

    console.print(f"✅ Found {len(rfq_data['products'])} product(s)\n")
    
    # Display products
    products_table = Table(title="Extracted Products")
    products_table.add_column("Product", style="cyan")
    products_table.add_column("Quantity", style="green")
    products_table.add_column("Specs", style="magenta")
    
    for product in rfq_data['products']:
        specs = product.get('specifications', {})
        specs_str = ", ".join([f"{k}: {v}" for k, v in specs.items()][:3])
        products_table.add_row(
            product['name'],
            str(product['quantity']),
            specs_str or "N/A"
        )
    
    console.print(products_table)
    console.print()
    
    # Initialize components
    summarizer = RFQSummarizer()
    selector = VendorSelector(CONFIG)
    
    # Store all results
    all_results = []
    
    # Login to ThomasNet
    headless_setting = headless if headless is not None else CONFIG.get("thomasnet", {}).get("headless", True)
    
    console.print("[yellow]🔐 Logging in to ThomasNet...[/yellow]")
    with ThomasNetAuth(headless=headless_setting) as auth:
        if not auth.page:
            console.print("[red]❌ Login failed or browser did not start[/red]")
            return

        search = ThomasNetSearch(auth)
        form_filler = RFQFormFiller(auth, CONFIG)
        
        # Process each product
        for product_idx, product in enumerate(rfq_data['products'], 1):
            console.print(f"\n[bold cyan]📦 Processing Product {product_idx}/{len(rfq_data['products'])}: {product['name']}[/bold cyan]\n")
            
            # 2. Search for vendors
            console.print("[yellow]🔍 Step 2: Searching ThomasNet vendors...[/yellow]")
            vendors = search.search_vendors(product['name'], max_results=20)
            
            if not vendors:
                console.print(f"[red]❌ No vendors found for {product['name']}[/red]")
                continue
            
            console.print(f"✅ Found {len(vendors)} vendor(s)\n")
            
            # 3. Select top vendors
            console.print(f"[yellow]🎯 Step 3: Selecting top {max_vendors} vendors...[/yellow]")
            selected_vendors = selector.select_top_vendors(vendors, product)
            
            # Display selected vendors
            vendors_table = Table(title=f"Selected Vendors for {product['name']}")
            vendors_table.add_column("Rank", style="cyan")
            vendors_table.add_column("Vendor", style="green")
            vendors_table.add_column("Score", style="yellow")
            vendors_table.add_column("Rating", style="magenta")
            vendors_table.add_column("Verified", style="blue")
            
            for vendor in selected_vendors:
                vendors_table.add_row(
                    str(vendor.get('rank')),
                    vendor['name'],
                    f"{vendor.get('selection_score', 0):.1f}",
                    f"{vendor.get('rating', 0)}/5.0",
                    "✓" if vendor.get('verified') else ""
                )
            
            console.print(vendors_table)
            console.print()
            
            if dry_run:
                console.print("[yellow]⏸️  Dry run - skipping submission[/yellow]\n")
                continue
            
            # 4. Generate summary
            console.print("[yellow]✍️  Step 4: Generating RFQ summary...[/yellow]")
            summary = summarizer.generate_summary(rfq_data, product)
            console.print(f"✅ Summary: {len(summary)} characters\n")
            console.print(f"[dim]{summary[:200]}...[/dim]\n")
            
            # 5. Submit to each vendor
            console.print(f"[yellow]📤 Step 5: Submitting to {len(selected_vendors)} vendors...[/yellow]\n")
            
            for vendor in track(selected_vendors, description="Submitting..."):
                result = form_filler.submit_rfq(
                    vendor=vendor,
                    summary=summary,
                    rfq_file_path=rfq
                )
                
                all_results.append({
                    'product': product['name'],
                    'vendor': vendor['name'],
                    'timestamp': datetime.now().isoformat(),
                    **result
                })
                
                if result['success']:
                    console.print(f"  ✅ {vendor['name']}: {result['confirmation_number']}")
                else:
                    console.print(f"  ❌ {vendor['name']}: {result.get('error','Unknown error')}")
    
    # 6. Save results
    results_file = log_dir / f"submissions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            'rfq_file': str(rfq),
            'timestamp': datetime.now().isoformat(),
            'products': rfq_data['products'],
            'submissions': all_results
        }, f, indent=2)
    
    console.print(f"\n[bold green]✅ Complete! Results saved to: {results_file}[/bold green]")
    
    # Summary
    successful = sum(1 for r in all_results if r.get('success'))
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Total submissions: {len(all_results)}")
    console.print(f"  Successful: {successful}")
    console.print(f"  Failed: {len(all_results) - successful}")


@cli.command()
@click.option('--directory', required=True, type=click.Path(exists=True), help='Directory with RFQ files')
@click.option('--headless/--no-headless', default=True, help='Run browser in headless mode')
def batch(directory, headless):
    """Batch process multiple RFQ files"""
    
    rfq_dir = Path(directory)
    # Find PDF and DOCX
    rfq_files = list(rfq_dir.glob('*.pdf')) + list(rfq_dir.glob('*.docx'))
    
    console.print(f"\n[bold blue]📁 Batch Processing {len(rfq_files)} RFQ files[/bold blue]\n")
    
    for rfq_file in rfq_files:
        console.print(f"\n{'='*80}")
        console.print(f"Processing: {rfq_file.name}")
        console.print('='*80)
        
        # Invoke submit command programmatically
        from click.testing import CliRunner
        runner = CliRunner()
        # Note: CliRunner isolates execution, but here we want side effects (logging, files)
        # Better to call function directly if possible, or use Context
        ctx = click.Context(submit)
        ctx.invoke(submit, rfq=str(rfq_file), headless=headless, max_vendors=5, dry_run=False)


@cli.command()
@click.argument('query')
@click.option('--headless/--no-headless', default=False)
def test_search(query, headless):
    """Test ThomasNet search functionality"""
    
    console.print(f"\n[bold blue]🔍 Testing search for: '{query}'[/bold blue]\n")
    
    with ThomasNetAuth(headless=headless) as auth:
        search = ThomasNetSearch(auth)
        vendors = search.search_vendors(query, max_results=10)
        
        table = Table(title=f"Search Results for '{query}'")
        table.add_column("Rank", style="cyan")
        table.add_column("Vendor", style="green")
        table.add_column("Location", style="yellow")
        table.add_column("Rating", style="magenta")
        
        for vendor in vendors:
            table.add_row(
                str(vendor.get('rank')),
                vendor['name'],
                vendor.get('location', ''),
                f"{vendor.get('rating', 0)}/5.0"
            )
        
        console.print(table)
        console.print(f"\n✅ Found {len(vendors)} vendors")

@cli.command()
def stats():
    """Show submission statistics"""
    import glob
    
    all_submissions = []
    log_files = list(log_dir.glob('submissions_*.json'))
    
    for file in log_files:
        try:
            with open(file) as f:
                data = json.load(f)
                all_submissions.extend(data.get('submissions', []))
        except:
            continue
    
    successful = sum(1 for s in all_submissions if s.get('success'))
    total = len(all_submissions)
    
    console.print(f"\n[bold]Submission Statistics[/bold]")
    console.print(f"Total Submissions: {total}")
    if total > 0:
        rate = (successful / total) * 100
        console.print(f"Successful: {successful} ({rate:.1f}%)")
    else:
        console.print("Successful: 0")
    console.print(f"Failed: {total - successful}")

if __name__ == '__main__':
    cli()
