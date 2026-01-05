import pdfplumber
import os

pdf = "N0010425QNF13.pdf"
base_path = "/Users/apple/Downloads/rebusinessautomationproject/data/solicitations/N0010425QNF13/attachments"
full_path = os.path.join(base_path, pdf)

# Focus on delivery and CLIN pages (typically 1-20 in Navy solicitations)
# and specification pages (around 50)
target_pages = [1, 2, 3, 4, 10, 11, 12, 13, 14, 15, 52]

with pdfplumber.open(full_path) as p:
    for page_num in target_pages:
        if page_num > len(p.pages): continue
        page = p.pages[page_num-1]
        print(f"--- PAGE {page_num} ---")
        print(page.extract_text())
        print("\n" + "="*50 + "\n")
