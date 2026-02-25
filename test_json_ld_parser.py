#!/usr/bin/env python3
"""
Test script to debug JSON-LD parsing from the saved HTML file.
"""

import json
from pathlib import Path
from bs4 import BeautifulSoup

def test_json_ld_parsing():
    """Test parsing JSON-LD from saved HTML."""
    
    html_file = Path("logs/search_results.html")
    
    if not html_file.exists():
        print(f"❌ File not found: {html_file}")
        return
    
    print(f"✅ Reading HTML from: {html_file}")
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all script tags with type="application/ld+json"
    json_ld_scripts = soup.find_all('script', {'type': 'application/ld+json'})
    
    print(f"\n📊 Found {len(json_ld_scripts)} JSON-LD script tags")
    
    for i, script in enumerate(json_ld_scripts):
        print(f"\n{'='*70}")
        print(f"Script #{i+1}")
        print('='*70)
        
        try:
            json_content = script.string
            if not json_content:
                print("⚠️  Script tag is empty")
                continue
                
            data = json.loads(json_content)
            
            print(f"✅ Successfully parsed JSON")
            print(f"Keys: {list(data.keys())}")
            
            # Check for @graph structure
            if "@graph" in data:
                print(f"\n✅ Found @graph with {len(data['@graph'])} items")
                
                for item in data["@graph"]:
                    if item.get("@id") == "#search-results":
                        print(f"\n🎯 Found #search-results!")
                        print(f"Type: {item.get('@type')}")
                        
                        if "itemListElement" in item:
                            vendors = item["itemListElement"]
                            print(f"✅ Found {len(vendors)} vendors in itemListElement")
                            
                            # Show first 3 vendors
                            for j, vendor_item in enumerate(vendors[:3]):
                                vendor = vendor_item.get("item", {})
                                print(f"\nVendor #{j+1}:")
                                print(f"  Name: {vendor.get('name')}")
                                print(f"  URL: {vendor.get('url')}")
                                address = vendor.get('address', {})
                                print(f"  Location: {address.get('addressLocality')}, {address.get('addressRegion')}")
                        else:
                            print("❌ No itemListElement found")
                            print(f"Available keys: {list(item.keys())}")
            else:
                print("⚠️  No @graph found")
                print(f"Data structure: {json.dumps(data, indent=2)[:500]}")
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            print(f"Content preview: {json_content[:200]}")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_json_ld_parsing()
