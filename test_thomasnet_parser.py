#!/usr/bin/env python3
"""
Test ThomasNet RFQ Parser
Tests the RFQ parser with existing RFQ files
"""

import sys
import json
from pathlib import Path

# Add ai_agents to path
sys.path.insert(0, str(Path(__file__).parent / "ai_agents"))

from ThomasNetAgent.rfq_parser import RFQParser

def test_parser():
    parser = RFQParser()
    
    # Test with markdown RFQ
    test_files = [
        "test_output_cdc0af15f8_service.md",
        "4866eaf56f_RFQ.md",
        "89d87524e3_RFQ_PRODUCT.md"
    ]
    
    print("=" * 60)
    print("Testing ThomasNet RFQ Parser")
    print("=" * 60)
    
    for test_file in test_files:
        file_path = Path(__file__).parent / test_file
        
        if not file_path.exists():
            print(f"\n⚠️  Skipping {test_file} - file not found")
            continue
            
        print(f"\n📄 Testing: {test_file}")
        print("-" * 60)
        
        try:
            result = parser.parse_file(str(file_path))
            
            # Validate structure
            assert 'products' in result, "Missing 'products' key"
            assert 'metadata' in result, "Missing 'metadata' key"
            
            print(f"✓ Parsed successfully")
            print(f"  Products found: {len(result['products'])}")
            print(f"  Metadata keys: {list(result['metadata'].keys())}")
            
            # Show first product if available
            if result['products']:
                product = result['products'][0]
                print(f"\n  First Product:")
                print(f"    Name: {product.get('name', 'N/A')}")
                print(f"    Quantity: {product.get('quantity', 'N/A')}")
                print(f"    Specs: {list(product.get('specifications', {}).keys())}")
            
            # Show metadata
            if result['metadata']:
                print(f"\n  Metadata:")
                for key, value in result['metadata'].items():
                    print(f"    {key}: {value}")
                    
        except Exception as e:
            print(f"✗ Error parsing {test_file}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Parser testing complete")
    print("=" * 60)

if __name__ == "__main__":
    test_parser()
