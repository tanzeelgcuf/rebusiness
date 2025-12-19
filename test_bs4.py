import sys
print("Importing bs4...", flush=True)
try:
    from bs4 import BeautifulSoup
    print("Success: BS4 imported", flush=True)
except Exception as e:
    print(f"Failed: {e}", flush=True)
