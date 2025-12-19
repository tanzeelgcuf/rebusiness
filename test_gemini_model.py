import os
import sys
import json
import urllib.request
import urllib.error
from unittest.mock import MagicMock

# 1. Mock google.generativeai BEFORE importing config to avoid hang
sys.modules['google.generativeai'] = MagicMock()

# 2. Import config to get API Key
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
import config

if not config.GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in config.")
    sys.exit(1)

api_key = config.GEMINI_API_KEY
print(f"DEBUG: Using API Key: {api_key[:5]}...")

models_to_test = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-001",
    "gemini-1.5-flash-latest",
    "gemini-pro",
    "gemini-1.0-pro"
]

prompt = {"contents": [{"parts": [{"text": "Hello, are you working?"}]}]}
data = json.dumps(prompt).encode('utf-8')
headers = {'Content-Type': 'application/json'}

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
print(f"--- Listing Available Models ---")
print(f"URL: {url}")

try:
    req = urllib.request.Request(url, headers=headers, method='GET')
    with urllib.request.urlopen(req, timeout=10) as response:
        print("SUCCESS! Status:", response.status)
        data = json.loads(response.read().decode('utf-8'))
        print("Available Models:")
        for m in data.get('models', []):
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                 print(f"- {m['name']}")
except urllib.error.HTTPError as e:
    print(f"FAILED: HTTP {e.code} - {e.reason}")
    print(f"Error Body: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"FAILED: {e}")
