"""
Template Structure Extractor

Extracts the exact structure from Claude Vendor List.odt and Claude Services List.odt
to create matching JSON schemas for the extraction system.
"""

from odf import text, teletype
from odf.opendocument import load
import json

def extract_template_structure(odt_file):
    """Extract text content from ODT file"""
    doc = load(odt_file)
    all_text = teletype.extractText(doc.text)
    return all_text

if __name__ == "__main__":
    print("="*80)
    print("CLAUDE VENDOR LIST (PRODUCT) TEMPLATE STRUCTURE")
    print("="*80)
    vendor_list = extract_template_structure('Claude Vendor List.odt')
    print(vendor_list[:5000])  # First 5000 characters
    
    print("\n" + "="*80)
    print("CLAUDE SERVICES LIST (SERVICE) TEMPLATE STRUCTURE")
    print("="*80)
    services_list = extract_template_structure('Claude Services List.odt')
    print(services_list[:5000])  # First 5000 characters
    
    # Save full content to files for analysis
    with open('template_analysis_product.txt', 'w') as f:
        f.write(vendor_list)
    
    with open('template_analysis_service.txt', 'w') as f:
        f.write(services_list)
    
    print("\n" + "="*80)
    print("Full templates saved to:")
    print("  - template_analysis_product.txt")
    print("  - template_analysis_service.txt")
