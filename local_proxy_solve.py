import os
import json
import time
from playwright.sync_api import sync_playwright

def solve_locally():
    """
    Launch a local browser to solve Captcha/Login.
    Crucially, it mimics the Linux Server's User-Agent to avoid mismatched cookies.
    """
    print("🚀 Launching local browser for ThomasNet...")
    print("   (Using Native User-Agent for stealth)")
    
    with sync_playwright() as p:
        # Launch standard headful chrome
        browser = p.chromium.launch(
            headless=False,
            # args=['--window-position=0,0']
        )
        
        context = browser.new_context(
            viewport={'width': 1366, 'height': 768}
            # user_agent=None (Use default)
        )
        page = context.new_page()
        
        print("🌐 Navigating to ThomasNet Suppliers...")
        try:
            # Go directly to the problem page
            page.goto("https://www.thomasnet.com/suppliers")
        except Exception as e:
            print(f"❌ Navigation error: {e}")

        print("\n" + "="*60)
        print("👉 ACTION REQUIRED:")
        print("1. Check the opened browser window.")
        print("2. If you see a CAPTCHA, solve it.")
        print("3. Ensure you are LOGGED IN (Sign In if needed).")
        print("4. Perform a test search manually to ensure it works.")
        print("="*60 + "\n")
        
        input("✅ Press ENTER here once you have solved everything and are logged in...")
        
        # Save state
        storage = context.storage_state()
        local_path = "auth_state.json"
        with open(local_path, "w") as f:
            json.dump(storage, f)
            
        print(f"🎉 Session saved to {local_path}")
        print("Now upload this file to the server:")
        print("gcloud compute scp auth_state.json rfq-dashboard:~/rebusinessautomationproject/dashboard/auth_state.json --zone us-central1-a --project samgov-478418")
        
        browser.close()

if __name__ == "__main__":
    solve_locally()
