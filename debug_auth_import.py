from ai_agents.ThomasNetAgent.auth import ThomasNetAuth
import time

def run():
    print("Testing ThomasNetAuth class directly...")
    try:
        # Try headless=True first as that worked in the raw debug script
        print("Initializing Auth (headless=True)...")
        auth = ThomasNetAuth(headless=True)
        print("Starting browser...")
        page = auth.start_browser()
        print("Browser started. Page object created.")
        print(f"Page title before nav: {page.title()}")
        auth.close()
        print("Auth closed successfully.")
        
        # Now try headless=False
        print("\nInitializing Auth (headless=False)...")
        auth = ThomasNetAuth(headless=False)
        print("Starting browser...")
        page = auth.start_browser()
        print("Browser started. Page object created.")
        auth.close()
        print("Auth closed successfully.")
        
    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run()
