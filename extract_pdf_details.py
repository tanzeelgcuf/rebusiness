import pdfplumber
import os

pdf_files = ["N0010425QNF13.pdf", "N0010425QNF130001.pdf"]
base_path = "/Users/apple/Downloads/rebusinessautomationproject/data/solicitations/N0010425QNF13/attachments"

keywords = ["delivery", "frequency", "spec", "MIL-", "ISO", "standard", "CLIN", "quality", "period of performance"]

for pdf in pdf_files:
    print(f"--- Analyzing {pdf} ---")
    full_path = os.path.join(base_path, pdf)
    if not os.path.exists(full_path):
        print(f"File not found: {full_path}")
        continue
        
    with pdfplumber.open(full_path) as p:
        for i, page in enumerate(p.pages):
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')
            for line in lines:
                if any(k.lower() in line.lower() for k in keywords):
                    print(f"Page {i+1}: {line.strip()}")
