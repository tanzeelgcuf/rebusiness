import os
import json
import time
from playwright.sync_api import sync_playwright

def solve_captcha_and_save():
    print("🚀 Launching browser via X11 forwarding...")
    
    with sync_playwright() as p:
        # Launch headful browser (shows on your Mac screen)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        
        print("🌐 Navigating to ThomasNet login...")
        page.goto("https://www.thomasnet.com/signin.html")
        
        print("\n" + "="*60)
        print("👉 ACTION REQUIRED:")
        print("1. Check the opened browser window on your Mac.")
        print("2. Solve any Captcha if present.")
        print("3. Log in manually if needed.")
        print("4. Navigate to 'https://www.thomasnet.com/suppliers' to verify access.")
        print("="*60 + "\n")
        
        input("✅ Press ENTER here once you are logged in and solved Captcha...")
        
        # Save state
        storage = context.storage_state()
        with open("dashboard/auth_state.json", "w") as f:
            json.dump(storage, f)
            
        print(f"🎉 Session saved to dashboard/auth_state.json")
        browser.close()

if __name__ == "__main__":
    solve_captcha_and_save()
