#!/usr/bin/env python3
"""
Save ThomasNet Session for Cloud/Headless Deployment
=====================================================
Run this script ONCE on your local Mac to log in to ThomasNet
and save the session cookies to dashboard/auth_state.json.

That file can then be uploaded to your Google Cloud server so
the dashboard can submit RFQs without needing a local Chrome window.

Usage:
    python3 save_thomasnet_session.py

What happens:
    1. A visible browser window opens
    2. You log in to ThomasNet manually (you have 90 seconds)
    3. Session is saved to dashboard/auth_state.json
    4. Upload that file to your cloud server
"""

import os
import sys
import time
from pathlib import Path

def save_session():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    # Save to dashboard/auth_state.json
    project_root = Path(__file__).parent
    auth_file = project_root / "dashboard" / "auth_state.json"
    auth_file.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  ThomasNet Session Saver")
    print("=" * 70)
    print()
    print("📋 Instructions:")
    print("   1. A browser window will open")
    print("   2. Log in to ThomasNet with your credentials")
    print("   3. Once logged in, come back here and press ENTER")
    print("   4. Session will be saved automatically")
    print()
    print(f"💾 Session will be saved to: {auth_file}")
    print()
    input("Press ENTER to open the browser...")
    print()

    with sync_playwright() as p:
        # Launch a VISIBLE browser (not headless) so you can log in
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
            ]
        )

        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        page = context.new_page()

        print("🌐 Opening ThomasNet login page...")
        page.goto("https://www.thomasnet.com/login/", timeout=30000)
        page.wait_for_load_state("networkidle")

        print()
        print("👆 Please log in to ThomasNet in the browser window.")
        print("   After logging in successfully, come back here.")
        print()
        input("Press ENTER after you have logged in to ThomasNet...")
        print()

        # Verify login
        print("🔍 Verifying login status...")
        current_url = page.url
        print(f"   Current URL: {current_url}")

        # Check for login indicators
        logged_in = False
        login_checks = [
            ("a[href*='account']", "account link"),
            ("a[href*='logout']", "logout link"),
            ("button:has-text('Sign Out')", "sign out button"),
            (".user-menu", "user menu"),
            ("#user-account", "user account"),
        ]

        for selector, name in login_checks:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=2000):
                    print(f"   ✅ Detected: {name}")
                    logged_in = True
                    break
            except:
                continue

        if not logged_in:
            # Check if we're NOT on login page (good sign)
            if 'login' not in current_url.lower() and 'signin' not in current_url.lower():
                print("   ✅ Not on login page — assuming logged in")
                logged_in = True
            else:
                print("   ⚠️  Could not confirm login. Saving anyway...")

        # Save the session
        print()
        print(f"💾 Saving session to {auth_file}...")
        context.storage_state(path=str(auth_file))

        browser.close()

    print()
    print("=" * 70)
    if auth_file.exists():
        size_kb = auth_file.stat().st_size / 1024
        print(f"✅ Session saved successfully!")
        print(f"   File: {auth_file}")
        print(f"   Size: {size_kb:.1f} KB")
        print()
        print("📤 Next steps for Google Cloud deployment:")
        print("   1. Upload auth_state.json to your cloud server:")
        print(f"      scp {auth_file} user@YOUR_CLOUD_IP:/path/to/project/dashboard/auth_state.json")
        print()
        print("   2. The dashboard will automatically use it for headless ThomasNet submissions")
        print()
        print("⚠️  IMPORTANT: Do NOT commit auth_state.json to Git (it contains login cookies)")
        print("   Add to .gitignore: dashboard/auth_state.json")
    else:
        print("❌ Session file was not created. Please try again.")
    print("=" * 70)

    # Auto-add to .gitignore
    gitignore_path = Path(__file__).parent / ".gitignore"
    gitignore_entry = "dashboard/auth_state.json\n"
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if "auth_state.json" not in content:
            with open(gitignore_path, 'a') as f:
                f.write(f"\n# ThomasNet session (contains login cookies - never commit)\n{gitignore_entry}")
            print(f"\n✅ Added auth_state.json to .gitignore")
    else:
        with open(gitignore_path, 'w') as f:
            f.write(f"# ThomasNet session (contains login cookies - never commit)\n{gitignore_entry}")
        print(f"\n✅ Created .gitignore with auth_state.json entry")


if __name__ == "__main__":
    save_session()
