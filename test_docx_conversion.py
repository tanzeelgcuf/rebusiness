from utils.doc_converter import convert_md_to_docx
import os

def test_conversion():
    files = ["bda4492a43_RFQ_PRODUCT.md", "f5949b6880_RFQ_SERVICE.md"]
    
    for f in files:
        if os.path.exists(f):
            print(f"Converting {f}...")
            with open(f, "r") as md_file:
                content = md_file.read()
            
            out_file = f.replace(".md", ".docx")
            if convert_md_to_docx(content, out_file):
                print(f"SUCCESS: Created {out_file}")
            else:
                print(f"FAILURE: Could not create {out_file}")
        else:
            print(f"Skipping {f} (not found)")

if __name__ == "__main__":
    test_conversion()
