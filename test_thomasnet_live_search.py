#!/usr/bin/env python3
"""
Test ThomasNet live search with manual login capability
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent

def test_live_search():
    """Test live search with manual login"""
    print("=" * 60)
    print("Testing ThomasNet Live Search (Manual Login)")
    print("=" * 60)
    print()
    print("⚠️  Browser will open (visible)")
    print("⚠️  Please log in manually if needed")
    print("⚠️  Solve any captchas that appear")
    print()
    input("Press Enter to continue...")
    print()
    
    # Initialize agent
    agent = ThomasNetAgent()
    
    # Test search query
    search_query = "CNC machining services"
    print(f"🔍 Searching for: {search_query}")
    print("-" * 60)
    
    try:
        # Perform search (API expects a dict with 'product_name' key)
        results = agent.find_suppliers_for_product(
            product={'product_name': search_query},
            limit=5
        )
        
        if results:
            print(f"\n✓ Found {len(results)} suppliers")
            print("-" * 60)
            
            for i, vendor in enumerate(results, 1):
                print(f"\n{i}. {vendor.get('name', 'Unknown')}")
                print(f"   Location: {vendor.get('location', 'N/A')}")
                print(f"   Rating: {vendor.get('rating', 'N/A')}")
                print(f"   Verified: {vendor.get('verified', 'N/A')}")
                if vendor.get('url'):
                    print(f"   URL: {vendor['url']}")
        else:
            print("\n❌ No suppliers found")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Close browser if auth object exists
        print("\n🔒 Closing browser...")
        if hasattr(agent, 'auth') and agent.auth:
            agent.auth.close()
        print("✓ Browser closed")
    
    print()
    print("=" * 60)
    print("Live search testing complete")
    print("=" * 60)

if __name__ == "__main__":
    test_live_search()
