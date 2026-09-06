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
        Optimized for the generated RFQ markdown format.
        """
        data = {
            "products": [],
            "metadata": {}
        }

        # 1. Extract Solicitation Number / Notice ID (more flexible patterns)
        solicitation_patterns = [
            r'Notice ID:\s*([A-Za-z0-9-]+)',
            r'(?:Solicitation Number|Solicitation No\.?|RFQ Number|RFQ ID)[:]\s*([A-Za-z0-9-]+)',
            r'(?:^|\n)\s*#\s*([A-Z0-9-]+)',
            r'(?:^|\n)\s*\*\*([A-Z0-9-]+)\*\*',
        ]
        for pattern in solicitation_patterns:
            solicitation_match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if solicitation_match:
                data["metadata"]["solicitation_number"] = solicitation_match.group(1).strip()
                break

        # 2. Extract Deadline (more flexible patterns)
        deadline_patterns = [
            r'(?:Response is needed on or before|Quotes Due|Due Date|Deadline|Response Date)[:]\s*([A-Za-z0-9\s,:-]+)',
            r'(?:Submit by|Due by)[:]\s*([A-Za-z0-9\s,:-]+)',
        ]
        for pattern in deadline_patterns:
            deadline_match = re.search(pattern, text, re.IGNORECASE)
            if deadline_match:
                data["metadata"]["deadline"] = deadline_match.group(1).strip()
                break

        # 3. Extract Products
        # Strategy A: Look for "### Item Requested:" (our generated RFQ format)
        item_section_match = re.search(r'###\s*Item Requested:\s*([^\n]+)', text, re.IGNORECASE)
        if item_section_match:
            product_name = item_section_match.group(1).strip()
            quantity = 1
            qty_match = re.search(r'(?:Quantity|Qty)[:]\s*(\d+)', text, re.IGNORECASE)
            if qty_match:
                quantity = int(qty_match.group(1))

            data["products"].append({
                "name": product_name,
                "quantity": quantity,
                "specifications": self._extract_specs(text)
            })

        # Strategy B: Look for markdown sections with product info
        if not data["products"]:
            product_section_match = re.search(r'##\s*(?:Product|Item|Service).*?\n(.*?)(?=\n##|\Z)', text, re.IGNORECASE | re.DOTALL)
            if product_section_match:
                section_text = product_section_match.group(1)
                name_match = re.search(r'(?:Name|Description|Title)[:]\s*([^\n]+)', section_text, re.IGNORECASE)
                qty_match = re.search(r'(?:Quantity|Qty|Amount)[:]\s*(\d+)', section_text, re.IGNORECASE)

                if name_match:
                    data["products"].append({
                        "name": name_match.group(1).strip(),
                        "quantity": int(qty_match.group(1)) if qty_match else 1,
                        "specifications": self._extract_specs(section_text)
                    })

        # Strategy C: Simple extraction for single-product RFQs
        if not data["products"]:
            product_patterns = [
                r'(?:Item Requested|Product Name|Service Name)[:]\s*([^\n]+)',
                r'\*\*(?:Product|Item|Service)[:]\*\*\s*([^\n]+)',
            ]
            for pattern in product_patterns:
                product_match = re.search(pattern, text, re.IGNORECASE)
                if product_match:
                    product_name = product_match.group(1).strip()
                    quantity = 1
                    qty_match = re.search(r'(?:Quantity|Qty)[:]\s*(\d+)', text, re.IGNORECASE)
                    if qty_match:
                        quantity = int(qty_match.group(1))

                    data["products"].append({
                        "name": product_name,
                        "quantity": quantity,
                        "specifications": self._extract_specs(text)
                    })
                    break

        # Strategy D: Parse CLIN table rows from markdown tables
        if not data["products"]:
            data["products"] = self._parse_clin_table_rows(text)

        # Strategy E: Check CLIN table logic (pipe-separated)
        if not data["products"]:
            clin_patterns = [
                r'(?:^|\n)\s*\|?\s*(\d{4})\s*\|?\s*([^|]+)\s*\|?\s*(\d+)',  # | 0001 | Widget | 10 |
                r'(?:^|\n)\s*CLIN\s*(\d+)[:]\s*([^\n]+)',
            ]
            for pattern in clin_patterns:
                clin_matches = re.finditer(pattern, text, re.MULTILINE)
                for match in clin_matches:
                    data["products"].append({
                        "clin": match.group(1),
                        "name": match.group(2).strip(),
                        "quantity": int(match.group(3)) if len(match.groups()) >= 3 else 1,
                        "specifications": {}
                    })

        # Fallback: Extract any description if no products found
        if not data["products"]:
            desc_match = re.search(r'(?:Description|Summary|Overview)[:]\s*([^\n]{20,})', text, re.IGNORECASE)
            if desc_match:
                data["products"].append({
                    "name": desc_match.group(1).strip()[:100],
                    "quantity": 1,
                    "specifications": self._extract_specs(text)
                })

        return data

    def _parse_clin_table_rows(self, text: str) -> List[Dict[str, Any]]:
        """Parse markdown pipe-delimited CLIN table rows."""
        products = []
        # Match rows like: | 0001 | Widget Assembly | 10 | EA | Base year |
        clin_row_pattern = r'\|\s*(\d{4})\s*\|\s*([^|]+)\s*\|\s*(\d+)\s*\|\s*([^|]*)\s*\|'
        matches = re.findall(clin_row_pattern, text)
        for match in matches:
            clin, description, qty, unit = match
            products.append({
                "clin": clin.strip(),
                "name": description.strip(),
                "quantity": int(qty.strip()),
                "unit": unit.strip() if unit.strip() else "EA",
                "specifications": self._extract_specs(text)
            })
        return products

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

        # Extract standards
        std_matches = re.findall(r'(MIL-STD-\d+|MIL-SPEC-\d+|ASTM D\d+|ISO \d+(?::\d+)?)', text)
        if std_matches:
            specs["Standards"] = ", ".join(set(std_matches))

        # Extract quantity from CLIN table if not already set
        total_qty = 0
        clin_row_pattern = r'\|\s*(\d{4})\s*\|\s*([^|]+)\s*\|\s*(\d+)\s*\|'
        for match in re.finditer(clin_row_pattern, text):
            total_qty += int(match.group(3).strip())
        if total_qty > 0:
            specs["Total_CLIN_Quantity"] = str(total_qty)

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
