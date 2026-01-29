import time
from auth import ThomasNetAuth

def setup_session():
    print("Opening browser for manual session setup...")
    print("Please:")
    print("1. Log in to ThomasNet")
    print("2. Solve any captchas")
    print("3. Ensure you can see the search bar")
    print("4. Close the browser window when done")
    
    # Force headless=False for manual interaction
    with ThomasNetAuth(headless=False) as auth:
        print("Browser launched. Waiting for you to close it...")
        # Keep script running until browser is closed
        try:
            while auth.context.pages:
                time.sleep(1)
        except Exception as e:
            print(f"Browser closed or disconnected: {e}")
            
    print("Session setup complete! Cookies/State should be saved in 'chrome_profile'.")

if __name__ == "__main__":
    setup_session()
