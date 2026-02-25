#!/usr/bin/env python3
"""
Test ThomasNet Authentication
Tests login flow with manual captcha solving capability
"""

import sys
import time
from pathlib import Path

# Add ai_agents to path
sys.path.insert(0, str(Path(__file__).parent / "ai_agents"))

from ThomasNetAgent.auth import ThomasNetAuth

def test_authentication():
    print("=" * 60)
    print("Testing ThomasNet Authentication")
    print("=" * 60)
    print("\n⚠️  This test will open a browser window")
    print("⚠️  You may need to solve a DataDome captcha manually")
    print("⚠️  Browser will stay open for 10 seconds after login\n")
    
    input("Press Enter to continue...")
    
    try:
        # Create auth instance with headless=False to see what's happening
        print("\n🌐 Starting browser...")
        auth = ThomasNetAuth(headless=False)
        
        # Start browser
        page = auth.start_browser()
        print("✓ Browser started successfully")
        
        # Attempt login
        print("\n🔐 Attempting login...")
        print("   (If captcha appears, please solve it manually)")
        
        success = auth.login()
        
        if success:
            print("\n✅ LOGIN SUCCESSFUL!")
            print(f"   Current URL: {page.url}")
            
            # Check for logged-in indicators
            if page.locator('text=Log Out').is_visible(timeout=2000):
                print("   ✓ 'Log Out' button found - definitely logged in")
            
            print("\n📸 Taking screenshot...")
            screenshot_path = Path("logs/auth_success.png")
            screenshot_path.parent.mkdir(exist_ok=True)
            page.screenshot(path=str(screenshot_path))
            print(f"   Screenshot saved to: {screenshot_path}")
            
            print("\n⏳ Keeping browser open for 10 seconds...")
            time.sleep(10)
            
        else:
            print("\n❌ LOGIN FAILED")
            print("   Check logs/login_error.png for screenshot")
            print("   Check logs/login_error.html for page source")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\n🔒 Closing browser...")
        auth.close()
        print("✓ Browser closed")
    
    print("\n" + "=" * 60)
    print("Authentication testing complete")
    print("=" * 60)

if __name__ == "__main__":
    test_authentication()
