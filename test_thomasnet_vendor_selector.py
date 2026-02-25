#!/usr/bin/env python3
"""
Test ThomasNet Vendor Selector
Tests vendor selection logic and scoring
"""

import sys
import json
from pathlib import Path

# Add ai_agents to path
sys.path.insert(0, str(Path(__file__).parent / "ai_agents"))

from ThomasNetAgent.vendor_selector import VendorSelector

def test_vendor_selector():
    print("=" * 60)
    print("Testing ThomasNet Vendor Selector")
    print("=" * 60)
    
    selector = VendorSelector()
    
    # Test vendors with various attributes
    test_vendors = [
        {
            "name": "Premium Vendor A",
            "url": "https://example.com/vendor-a",
            "rating": 4.8,
            "verified": True,
            "rank": 1,
            "location": "California, USA"
        },
        {
            "name": "Good Vendor B",
            "url": "https://example.com/vendor-b",
            "rating": 4.2,
            "verified": True,
            "rank": 2,
            "location": "Texas, USA"
        },
        {
            "name": "Average Vendor C",
            "url": "https://example.com/vendor-c",
            "rating": 3.5,
            "verified": False,
            "rank": 3,
            "location": "New York, USA"
        },
        {
            "name": "Low Rating Vendor D",
            "url": "https://example.com/vendor-d",
            "rating": 2.5,
            "verified": False,
            "rank": 4,
            "location": "Florida, USA"
        },
        {
            "name": "New Vendor E (No Rating)",
            "url": "https://example.com/vendor-e",
            "rating": 0.0,
            "verified": True,
            "rank": 5,
            "location": "Ohio, USA"
        },
        {
            "name": "Vendor F",
            "url": "https://example.com/vendor-f",
            "rating": 4.0,
            "verified": False,
            "rank": 6,
            "location": "Michigan, USA"
        },
    ]
    
    print(f"\n📊 Input: {len(test_vendors)} test vendors")
    print("-" * 60)
    
    # Test selection
    product_data = {"name": "Industrial Fasteners"}
    selected = selector.select_top_vendors(test_vendors, product_data)
    
    print(f"\n✓ Selected {len(selected)} vendors")
    print("-" * 60)
    
    for i, vendor in enumerate(selected, 1):
        print(f"\n{i}. {vendor['name']}")
        print(f"   Score: {vendor.get('selection_score', 0):.2f}")
        print(f"   Rating: {vendor.get('rating', 0):.1f}/5.0")
        print(f"   Verified: {'Yes' if vendor.get('verified') else 'No'}")
        print(f"   Rank: #{vendor.get('rank')}")
        print(f"   Location: {vendor.get('location', 'Unknown')}")
    
    # Verify selection criteria
    print("\n" + "=" * 60)
    print("Validation Checks:")
    print("=" * 60)
    
    # Check max vendors
    max_vendors = 5
    assert len(selected) <= max_vendors, f"Too many vendors selected (max: {max_vendors})"
    print(f"✓ Respects max vendors limit ({max_vendors})")
    
    # Check min rating (should filter out 2.5 rating vendor)
    min_rating = 3.0
    for vendor in selected:
        rating = vendor.get('rating', 0)
        if rating > 0:  # Only check if rating is known
            assert rating >= min_rating, f"Vendor {vendor['name']} has rating {rating} < {min_rating}"
    print(f"✓ All vendors meet minimum rating ({min_rating})")
    
    # Check sorting by score
    scores = [v.get('selection_score', 0) for v in selected]
    assert scores == sorted(scores, reverse=True), "Vendors not sorted by score"
    print(f"✓ Vendors sorted by selection score")
    
    print("\n" + "=" * 60)
    print("Vendor selector testing complete")
    print("=" * 60)

if __name__ == "__main__":
    test_vendor_selector()
