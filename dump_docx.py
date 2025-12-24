
import sys
import os
import zipfile
import re

FILE_PATH = "/Users/apple/Downloads/rebusinessautomationproject/data/solicitations/483f26d1ad/attachments/36C26126P0265_1.docx"

def get_docx_text(path):
    try:
        with zipfile.ZipFile(path) as document:
            xml_content = document.read('word/document.xml')
        
        # Very basic XML parsing to get text
        text = str(xml_content)
        # Remove tags
        clean_text = re.sub('<[^<]+?>', ' ', text)
        return clean_text
    except Exception as e:
        return f"Error reading DOCX: {e}"

print(get_docx_text(FILE_PATH))
