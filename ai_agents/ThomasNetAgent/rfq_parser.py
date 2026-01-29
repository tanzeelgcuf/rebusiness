import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import re
import json

# Import parsers
import PyPDF2
from docx import Document

logger = logging.getLogger(__name__)

class RFQParser:
    """
    Parses RFQ documents to extract structured data for ThomasNet submission.
    Supports PDF, DOCX, and MD formats.
    """
    
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse an RFQ file and extract key information.
        
        Args:
            file_path: Path to the RFQ file
            
        Returns:
            Dictionary containing extracted products and metadata
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"RFQ file not found: {file_path}")
            
        logger.info(f"Parsing RFQ: {path.name}")
        
        text = ""
        
        # Dispatch based on extension
        if path.suffix.lower() == '.pdf':
            text = self._read_pdf(path)
        elif path.suffix.lower() == '.docx':
            text = self._read_docx(path)
        elif path.suffix.lower() == '.md':
            text = self._read_markdown(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
            
        return self._extract_data_from_text(text)

    def _read_pdf(self, path: Path) -> str:
        """Extract text from PDF."""
        text = ""
        try:
            with open(path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            logger.error(f"Error reading PDF: {e}")
        return text

    def _read_docx(self, path: Path) -> str:
        """Extract text from DOCX."""
        text = ""
        try:
            doc = Document(path)
            # Read paragraphs
            for para in doc.paragraphs:
                text += para.text + "\n"
            # Read tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text for cell in row.cells]
                    text += " | ".join(row_text) + "\n"
        except Exception as e:
            logger.error(f"Error reading DOCX: {e}")
        return text
        
    def _read_markdown(self, path: Path) -> str:
        """Read markdown file."""
        try:
            return path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Error reading Markdown: {e}")
            return ""

    def _extract_data_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract structured data from raw text using regex and heuristics.
        """
        data = {
            "products": [],
            "metadata": {}
        }
        
        # 1. Extract Solicitation Number / Notice ID
        # Patterns: Notice ID: X, Solicitation Number: Y
        solicitation_match = re.search(r'(?:Notice ID|Solicitation Number|Solicitation No\.?):\s*([A-Za-z0-9-]+)', text, re.IGNORECASE)
        if solicitation_match:
            data["metadata"]["solicitation_number"] = solicitation_match.group(1).strip()
            
        # 2. Extract Deadline
        # Patterns: Response needed on or before [Date], Quotes Due: [Date]
        deadline_match = re.search(r'(?:Response is needed on or before|Quotes Due|Due Date):\s*([A-Za-z0-9\s,]+)', text, re.IGNORECASE)
        if deadline_match:
            data["metadata"]["deadline"] = deadline_match.group(1).strip()
            
        # 3. Extract Products
        # Strategies:
        # A. Look for "Item Requested:" or "Items Required" sections
        # B. Look for CLIN tables (line items)
        
        # Simple extraction for single-product RFQs (common in this workflow)
        product_match = re.search(r'(?:Item Requested|Product Name):\s*([^\n]+)', text, re.IGNORECASE)
        
        if product_match:
            product_name = product_match.group(1).strip()
            # Try to find quantity nearby
            quantity = 1 # Default
            qty_match = re.search(r'(?:Quantity|Qty):\s*(\d+)', text, re.IGNORECASE)
            if qty_match:
                quantity = int(qty_match.group(1))
                
            data["products"].append({
                "name": product_name,
                "quantity": quantity,
                "specifications": self._extract_specs(text)
            })
            
        # Fallback: Check CLIN table logic if no main product found
        if not data["products"]:
            # Look for lines starting with CLIN numbers e.g., "0001 | Widget | 10"
            clin_matches = re.finditer(r'(?:^|\n)\s*(\d{4})\s*[|]\s*([^|]+)\s*[|]\s*(\d+)', text)
            for match in clin_matches:
                data["products"].append({
                    "clin": match.group(1),
                    "name": match.group(2).strip(),
                    "quantity": int(match.group(3)),
                    "specifications": {}
                })
                
        return data

    def _extract_specs(self, text: str) -> Dict[str, str]:
        """Extract technical specifications."""
        specs = {}
        
        # Extract NSN
        nsn_match = re.search(r'NSN:\s*([\d-]+)', text)
        if nsn_match:
            specs["NSN"] = nsn_match.group(1)
            
        # Extract Part Number
        pn_match = re.search(r'(?:Part Number|P/N|MPN):\s*([^\n]+)', text, re.IGNORECASE)
        if pn_match:
            specs["Part Number"] = pn_match.group(1).strip()
            
        # Extract Manufacturer / CAGE
        cage_match = re.search(r'(?:CAGE Code|CAGE):\s*([A-Z0-9]+)', text, re.IGNORECASE)
        if cage_match:
            specs["CAGE"] = cage_match.group(1)
            
        return specs

if __name__ == "__main__":
    # Test block
    import sys
    if len(sys.argv) > 1:
        parser = RFQParser()
        try:
            result = parser.parse_file(sys.argv[1])
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python rfq_parser.py <path_to_rfq_file>")
