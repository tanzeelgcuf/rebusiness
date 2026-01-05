import sys
print(f"Python: {sys.executable}")

try:
    import pdfplumber
    print("Pdfplumber: OK")
except Exception as e:
    print(f"Pdfplumber: FAIL {e}")
