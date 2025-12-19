import sys
from unittest.mock import MagicMock

print("Mocking html5lib...", flush=True)
sys.modules['html5lib'] = MagicMock()

print("Importing bs4...", flush=True)
try:
    from bs4 import BeautifulSoup
    print("Success: BS4 imported with mock", flush=True)
except Exception as e:
    print(f"Failed: {e}", flush=True)
