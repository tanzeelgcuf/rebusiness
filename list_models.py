import google.generativeai as genai
import os
import sys

# Add path to config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
import config

genai.configure(api_key=config.GEMINI_API_KEY)

print("Listing available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")
