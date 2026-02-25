#!/usr/bin/env python3
import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

def save_session():
    """
    Opens a browser for manual login and saves the session state to auth_state.json
    """
    print("\n" + "="*70)
    print("ThomasNet Session Saver")
    print("="*70)
    print("This script will open a browser for you to log in to ThomasNet.")
    print("Once logged in, the session will be saved for the server to use.")
    print("="*70 + "\n")

    with sync_playwright() as p:
        # Launch browser in headed mode for user to log in
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto("https://www.thomasnet.com")
        
        print("ACTION REQUIRED:")
        print("1. Log in to ThomasNet in the opened Chrome window.")
        print("2. Solve any captchas if they appear.")
        print("3. Once you see your account dashboard/home page, come back here.")
        
        input("\nPress Enter here after you have successfully logged in...")
        
        # Save storage state
        auth_path = Path("auth_state.json")
        context.storage_state(path=str(auth_path))
        
        print(f"\n✅ Session saved to {auth_path.absolute()}")
        print("You can now close the browser window.")
        
        browser.close()

if __name__ == "__main__":
    save_session()
