
import pdfplumber
import re
import os

pdf_path = "data/solicitations/N0010425QNF13/attachments/N0010425QNF13.pdf"

with pdfplumber.open(pdf_path) as pdf:
    full_text = ""
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            full_text += f"\n--- PAGE {i+1} ---\n{text}"

print("Full Text Length:", len(full_text))

# Find ITEM NAME
match = re.search(r'ITEM NAME', full_text)
if match:
    print(f"Found ITEM NAME at {match.start()}")
    print("Context:")
    print(full_text[match.start():match.start()+500])
else:
    print("ITEM NAME not found in full text.")

# Find CLIN 0001
match_clin = re.search(r'0001', full_text)
if match_clin:
    print(f"Found 0001 at {match_clin.start()}")
    print("Context:")
    print(full_text[match_clin.start():match_clin.start()+500])
else:
    print("0001 not found.")
