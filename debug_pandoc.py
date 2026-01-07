import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"Sys Path: {sys.path}")

try:
    import pypandoc
    print("Success: import pypandoc")
    print(f"Pypandoc file: {pypandoc.__file__}")
except ImportError as e:
    print(f"Failed: import pypandoc ({e})")
    
try:
    import pypandoc_binary
    print("Success: import pypandoc_binary")
except ImportError as e:
    print(f"Failed: import pypandoc_binary ({e})")

try:
    import docx
    print("Success: import docx")
except ImportError as e:
    print(f"Failed: import docx ({e})")
