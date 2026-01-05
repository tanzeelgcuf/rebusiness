import sys
print(f"Python: {sys.executable}")
try:
    import capsolver
    print("Capsolver: OK")
except Exception as e:
    print(f"Capsolver: FAIL {e}")

try:
    import pdfplumber
    print("Pdfplumber: OK")
except Exception as e:
    print(f"Pdfplumber: FAIL {e}")
