
import sys
import os

# Check imports
try:
    from google import genai
    from google.genai import types
    import pdfplumber
    print("SUCCESS: Imports work!")
except ImportError as e:
    print(f"FAILURE: Import error: {e}")
    sys.exit(1)

# Check pdfplumber on a mock file if possible, or just print success
print(f"pdfplumber version: {pdfplumber.__version__}")

# Check genai client init
try:
    sys.path.append(os.path.abspath(os.curdir))
    import config
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    print("SUCCESS: GenAI client initialized!")
except Exception as e:
    print(f"FAILURE: GenAI client init error: {e}")
