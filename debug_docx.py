import docx
import sys

try:
    doc = docx.Document('rfq_downloads/2026-01-08/19158a1ec5_RFQ_SERVICE.docx')
    text = '\n'.join([p.text for p in doc.paragraphs])
    print(text)
    
    print("\n--- TABLE CHECK ---")
    print(f"Contains '|': {'|' in text}")
    print(f"Pipe count: {text.count('|')}")
    
    print("\n--- EMAIL CHECK ---")
    if '.gov' in text:
        print("Found '.gov' at:")
        start = text.find('.gov') - 20
        end = start + 50
        print(f"...{text[start:end]}...")

except Exception as e:
    print(e)
