#!/usr/bin/env python3
"""
Find your Chrome user data directory.
This is needed to connect Playwright to your real Chrome profile.
"""
import os
import platform

def find_chrome_profile():
    """Locate Chrome user data directory based on OS"""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        paths = [
            os.path.expanduser("~/Library/Application Support/Google/Chrome"),
            os.path.expanduser("~/Library/Application Support/Google/Chrome/Default"),
        ]
    elif system == "Windows":
        paths = [
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data"),
        ]
    else:  # Linux
        paths = [
            os.path.expanduser("~/.config/google-chrome"),
        ]
    
    print("Searching for Chrome profile...\n")
    for path in paths:
        if os.path.exists(path):
            print(f"✓ Found: {path}")
            return path
    
    print("✗ Chrome profile not found in default locations.")
    print("\nTo find manually:")
    print("1. Open Chrome")
    print("2. Go to: chrome://version")
    print("3. Look for 'Profile Path' or 'User Data Directory'")
    return None

if __name__ == "__main__":
    profile = find_chrome_profile()
    if profile:
        print(f"\nUse this path in the script: {profile}")
