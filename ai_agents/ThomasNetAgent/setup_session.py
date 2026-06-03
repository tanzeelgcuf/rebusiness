import time
import sys
import os
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth import ThomasNetAuth, SESSION_FILE

def setup_session():
    print("\n" + "="*60)
    print("THOMASNET SESSION SETUP (DATA DOME BYPASS SEEDING)")
    print("="*60)
    print("\nThis script will open a browser for you to manually log in.")
    print("This 'seeds' a valid session that the automation can reuse.")
    print("\nSTEPS:")
    print("1. A browser window will open.")
    print("2. Navigate to ThomasNet and LOG IN if prompted.")
    print("3. Solve any DataDome CAPTCHAs that appear.")
    print("4. Once you are successfully on the dashboard/search page,")
    print("   come back to this terminal and press ENTER.")
    print("="*60 + "\n")
    
    # Initialize auth in non-headless mode
    # We pass storage_state=None to ensure we start fresh if needed, 
    # or it will naturally load the existing one if we want to 'refresh' it.
    auth = ThomasNetAuth(headless=False)
    page = auth.start_browser()
    
    try:
        print("Opening ThomasNet...")
        page.goto("https://www.thomasnet.com", wait_until="domcontentloaded")
        
        input(">>> Press ENTER here once you have logged in and solved all CAPTCHAs...")
        
        print("\nSaving session state...")
        auth.save_session()
        print(f"✅ Session saved successfully to: {SESSION_FILE}")
        
    except Exception as e:
        print(f"❌ Error during setup: {e}")
    finally:
        auth.close()

    print("\n" + "="*60)
    print("SETUP COMPLETE")
    print("You can now run the automation in headless mode.")
    print("="*60 + "\n")

if __name__ == "__main__":
    setup_session()
