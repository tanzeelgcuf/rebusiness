#!/usr/bin/env python3
"""
Test script for enhanced email discovery methods.
Tests the new email extraction capabilities.
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from ai_agents.MappingAgent.mapping_agent import MappingAgent

def test_email_discovery():
    """Test enhanced email discovery on a known vendor."""
    
    print("=" * 80)
    print("TESTING ENHANCED EMAIL DISCOVERY")
    print("=" * 80)
    
    agent = MappingAgent()
    
    # Test vendor with known website
    test_vendor = "Teledyne LeCroy"
    test_website = "https://www.teledynelecroy.com"
    test_agency = "Department of Defense"
    
    print(f"\nTesting deep crawl for: {test_vendor}")
    print(f"Website: {test_website}")
    print("-" * 80)
    
    # Test deep crawl with enhanced email extraction
    details = agent._deep_crawl_vendor(test_vendor, test_website, test_agency)
    
    print("\n" + "=" * 80)
    print("RESULTS:")
    print("=" * 80)
    print(f"Email found: {details.get('email')}")
    print(f"Has government page: {details.get('has_gov_page')}")
    print(f"LinkedIn: {details.get('linkedin_url')}")
    
    agent.close()
    print("\nTest complete!")

if __name__ == "__main__":
    test_email_discovery()
