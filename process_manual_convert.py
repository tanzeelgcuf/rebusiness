import os
import sys
# Add path to import utils
sys.path.append(os.getcwd())
from utils.doc_converter import convert_md_to_docx

md_path = "rfq_downloads/2026-01-08/371a4ef263_RFQ_SERVICE.md"
docx_path = md_path.replace(".md", ".docx")

if not os.path.exists(md_path):
    print(f"Error: MD file not found at {md_path}")
    sys.exit(1)
    
print(f"Converting {md_path}...")
with open(md_path, 'r', encoding='utf-8') as f:
    content = f.read()
    
if convert_md_to_docx(content, docx_path):
    print(f"Success! Created {docx_path}")
else:
    print("Conversion failed.")
