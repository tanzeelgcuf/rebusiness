#!/usr/bin/env python3
"""
Test ThomasNet Config Loading
Validates configuration file and environment variables
"""

import sys
from pathlib import Path

# Add ai_agents to path
sys.path.insert(0, str(Path(__file__).parent / "ai_agents"))

def test_config():
    print("=" * 60)
    print("Testing ThomasNet Configuration")
    print("=" * 60)
    
    # Test 1: Config file loading
    print("\n📋 Test 1: Config File Loading")
    print("-" * 60)
    
    try:
        from ThomasNetAgent.auth import CONFIG
        print("✓ Config loaded successfully")
        
        # Validate structure
        assert 'thomasnet' in CONFIG, "Missing 'thomasnet' section"
        print("✓ Has 'thomasnet' section")
        
        # Check required keys
        required_keys = ['base_url', 'login_url', 'browser_timeout', 'headless']
        for key in required_keys:
            assert key in CONFIG['thomasnet'], f"Missing key: {key}"
            print(f"✓ Has '{key}': {CONFIG['thomasnet'][key]}")
            
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        return False
    
    # Test 2: Environment variables
    print("\n🔐 Test 2: Environment Variables")
    print("-" * 60)
    
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        email = os.getenv('THOMASNET_EMAIL')
        password = os.getenv('THOMASNET_PASSWORD')
        proxy = os.getenv('THOMASNET_PROXY')
        
        if email:
            print(f"✓ THOMASNET_EMAIL: {email}")
        else:
            print("⚠️  THOMASNET_EMAIL not set")
            
        if password:
            print(f"✓ THOMASNET_PASSWORD: {'*' * len(password)}")
        else:
            print("⚠️  THOMASNET_PASSWORD not set")
            
        if proxy:
            print(f"✓ THOMASNET_PROXY: {proxy}")
        else:
            print("ℹ️  THOMASNET_PROXY not set (optional)")
            
        if not email or not password:
            print("\n⚠️  WARNING: Missing required credentials!")
            print("   Authentication tests will fail without these.")
            
    except Exception as e:
        print(f"✗ Environment check failed: {e}")
        return False
    
    # Test 3: Vendor selection config
    print("\n🎯 Test 3: Vendor Selection Config")
    print("-" * 60)
    
    try:
        if 'vendor_selection' in CONFIG:
            vs_config = CONFIG['vendor_selection']
            print(f"✓ Max vendors per product: {vs_config.get('max_vendors_per_product', 'N/A')}")
            print(f"✓ Min rating: {vs_config.get('min_rating', 'N/A')}")
            print(f"✓ Require verification: {vs_config.get('require_verification', 'N/A')}")
        else:
            print("⚠️  No vendor_selection config found")
            
    except Exception as e:
        print(f"✗ Vendor config check failed: {e}")
    
    # Test 4: Company info
    print("\n🏢 Test 4: Company Information")
    print("-" * 60)
    
    try:
        if 'company' in CONFIG:
            company = CONFIG['company']
            print(f"✓ Company name: {company.get('name', 'N/A')}")
            print(f"✓ Contact name: {company.get('contact_name', 'N/A')}")
            print(f"✓ Email: {company.get('email', 'N/A')}")
            print(f"✓ Phone: {company.get('phone', 'N/A')}")
        else:
            print("⚠️  No company config found")
            
    except Exception as e:
        print(f"✗ Company config check failed: {e}")
    
    print("\n" + "=" * 60)
    print("Configuration testing complete")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = test_config()
    sys.exit(0 if success else 1)
