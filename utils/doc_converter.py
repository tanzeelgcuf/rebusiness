"""
Enhanced DOCX Converter
Ensures perfect conversion from Markdown to DOCX format
Maintains tables, formatting, and structure from templates
"""
import os
import re
import logging
from typing import Optional, List
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)

try:
    import pypandoc
    PYPANDOC_AVAILABLE = True
except ImportError:
    PYPANDOC_AVAILABLE = False
    logger.warning("pypandoc not available, will use python-docx only")


class EnhancedDocConverter:
    """
    Advanced Markdown to DOCX converter with template compliance.
    Handles tables, emojis, and complex formatting.
    """
    
    def __init__(self, reference_doc_path: Optional[str] = None):
        """
        Initialize converter.
        
        Args:
            reference_doc_path: Path to reference .docx for styling
        """
        self.reference_doc_path = reference_doc_path
        
        # Styling configuration
        self.styles = {
            'heading1': {'size': 16, 'bold': True, 'color': RGBColor(0, 0, 0)},
            'heading2': {'size': 14, 'bold': True, 'color': RGBColor(0, 0, 0)},
            'normal': {'size': 11, 'bold': False, 'color': RGBColor(0, 0, 0)},
            'emphasis': {'size': 11, 'bold': True, 'color': RGBColor(0, 0, 0)}
        }
    
    def clean_markdown(self, markdown_content: str) -> str:
        """
        Pre-process markdown to ensure clean conversion.
        """
        # Remove HTML comments
        markdown_content = re.sub(r'<!--.*?-->', '', markdown_content, flags=re.DOTALL)
        
        # Remove HTML tags
        markdown_content = re.sub(r'<[^>]+>', '', markdown_content)
        
        # Remove excess blank lines (max 2)
        markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
        
        # Remove any ** formatting (should already be done, but safety)
        markdown_content = markdown_content.replace('**', '')
        
        # Scrub government emails (CRITICAL)
        gov_email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(?:gov|mil)\b'
        markdown_content = re.sub(gov_email_pattern, 'john@campsable.com', markdown_content, flags=re.IGNORECASE)
        
        # Ensure proper table formatting
        lines = markdown_content.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            # Add blank line before table if needed
            if '|' in line and line.strip().startswith('|'):
                if i > 0 and '|' not in lines[i-1] and cleaned_lines and cleaned_lines[-1].strip():
                    cleaned_lines.append('')
                cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def convert_with_pypandoc(self, markdown_content: str, output_path: str) -> bool:
        """
        Convert using pypandoc (preferred method for tables).
        """
        if not PYPANDOC_AVAILABLE:
            return False
        
        try:
            cleaned_content = self.clean_markdown(markdown_content)
            
            extra_args = []
            if self.reference_doc_path and os.path.exists(self.reference_doc_path):
                extra_args.append(f'--reference-doc={self.reference_doc_path}')
            
            # Use GFM (GitHub Flavored Markdown) for better table support
            pypandoc.convert_text(
                cleaned_content,
                'docx',
                format='gfm',
                outputfile=output_path,
                extra_args=extra_args
            )
            
            # Verify output
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"pypandoc conversion successful: {output_path}")
                return True
            else:
                logger.error("pypandoc produced empty file")
                return False
                
        except Exception as e:
            logger.error(f"pypandoc conversion failed: {e}")
            return False
    
    def convert_with_docx(self, markdown_content: str, output_path: str) -> bool:
        """
        Fallback conversion using python-docx directly.
        More control but requires manual parsing.
        """
        try:
            cleaned_content = self.clean_markdown(markdown_content)
            doc = Document()
            
            # Parse and add content
            lines = cleaned_content.split('\n')
            i = 0
            
            while i < len(lines):
                line = lines[i].strip()
                
                if not line:
                    i += 1
                    continue
                
                # Heading detection
                if line.startswith('## '):
                    self._add_heading(doc, line[3:].strip(), level=2)
                elif line.startswith('# '):
                    self._add_heading(doc, line[2:].strip(), level=1)
                
                # Table detection
                elif '|' in line and line.startswith('|'):
                    table_lines = []
                    while i < len(lines) and '|' in lines[i]:
                        table_lines.append(lines[i].strip())
                        i += 1
                    self._add_table(doc, table_lines)
                    continue
                
                # Horizontal rule
                elif line.startswith('---'):
                    self._add_horizontal_line(doc)
                
                # Bullet list
                elif line.startswith('- '):
                    self._add_paragraph(doc, line[2:], style='List Bullet')
                
                # Checkbox list (for SERVICE RFQs)
                elif line.startswith('- [ ]'):
                    self._add_paragraph(doc, '☐ ' + line[5:], style='List Bullet')
                elif line.startswith('- [x]'):
                    self._add_paragraph(doc, '☑ ' + line[5:], style='List Bullet')
                
                # Regular paragraph
                else:
                    self._add_paragraph(doc, line)
                
                i += 1
            
            # Save document
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            doc.save(output_path)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"python-docx conversion successful: {output_path}")
                return True
            else:
                logger.error("python-docx produced empty file")
                return False
                
        except Exception as e:
            logger.error(f"python-docx conversion failed: {e}")
            return False
    
    def _add_heading(self, doc: Document, text: str, level: int = 2):
        """Add heading with emoji support."""
        heading = doc.add_heading(text, level=level)
        # Ensure emoji rendering (they should pass through)
        run = heading.runs[0] if heading.runs else None
        if run:
            run.font.size = Pt(self.styles.get(f'heading{level}', {}).get('size', 14))
    
    def _add_paragraph(self, doc: Document, text: str, style: str = 'Normal'):
        """Add paragraph with proper formatting."""
        p = doc.add_paragraph(text, style=style)
        # Apply font size
        for run in p.runs:
            run.font.size = Pt(self.styles['normal']['size'])
    
    def _add_table(self, doc: Document, table_lines: List[str]):
        """
        Parse and add markdown table to document.
        Handles pipe-delimited format.
        """
        if not table_lines:
            return
        
        # Parse table rows
        rows = []
        for line in table_lines:
            # Skip separator lines (|---|---|)
            if re.match(r'^\|[\s\-:]+\|$', line):
                continue
            
            # Split by pipe and clean
            cells = [cell.strip() for cell in line.split('|')]
            cells = [c for c in cells if c]  # Remove empty
            
            if cells:
                rows.append(cells)
        
        if not rows:
            return
        
        # Determine column count
        max_cols = max(len(row) for row in rows)
        
        # Create table
        table = doc.add_table(rows=len(rows), cols=max_cols)
        table.style = 'Table Grid'
        
        # Populate cells
        for i, row_data in enumerate(rows):
            row = table.rows[i]
            for j, cell_data in enumerate(row_data):
                if j < len(row.cells):
                    row.cells[j].text = cell_data
                    # Format header row (first row) in bold
                    if i == 0:
                        for paragraph in row.cells[j].paragraphs:
                            for run in paragraph.runs:
                                run.font.bold = True
                                run.font.size = Pt(10)
    
    def _add_horizontal_line(self, doc: Document):
        """Add horizontal line separator."""
        p = doc.add_paragraph()
        p.paragraph_format.border_bottom = True
    
    def convert(self, markdown_content: str, output_path: str) -> bool:
        """
        Main conversion method with fallback chain.
        """
        logger.info(f"Converting RFQ to DOCX: {output_path}")
        
        # Strategy 1: Try pypandoc first (best for tables)
        if PYPANDOC_AVAILABLE:
            if self.convert_with_pypandoc(markdown_content, output_path):
                return True
            logger.warning("pypandoc failed, falling back to python-docx")
        
        # Strategy 2: Use python-docx
        if self.convert_with_docx(markdown_content, output_path):
            return True
        
        # Strategy 3: Last resort - save as markdown
        logger.error("All conversion methods failed, saving as .md")
        md_path = output_path.replace('.docx', '.md')
        try:
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(self.clean_markdown(markdown_content))
            logger.info(f"Saved as markdown: {md_path}")
            return False
        except Exception as e:
            logger.error(f"Even markdown save failed: {e}")
            return False


def convert_md_to_docx(markdown_content: str, output_path: str, reference_doc: str = None) -> bool:
    """
    Public API for markdown to DOCX conversion.
    
    Args:
        markdown_content: Raw markdown string
        output_path: Destination .docx file path
        reference_doc: Optional reference document for styling
    
    Returns:
        True if successful, False otherwise
    """
    converter = EnhancedDocConverter(reference_doc_path=reference_doc)
    return converter.convert(markdown_content, output_path)


# ==================== VALIDATION HELPER ====================

def validate_docx_quality(docx_path: str) -> dict:
    """
    Quick validation of converted DOCX.
    Returns basic quality metrics.
    """
    try:
        doc = Document(docx_path)
        
        paragraph_count = len(doc.paragraphs)
        table_count = len(doc.tables)
        char_count = sum(len(p.text) for p in doc.paragraphs)
        
        # Check for emojis (should be preserved)
        full_text = '\n'.join([p.text for p in doc.paragraphs])
        has_emojis = any(emoji in full_text for emoji in ['🏛️', '🟩'])
        
        # Check for government emails (should be none)
        gov_email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(?:gov|mil)\b'
        gov_emails = re.findall(gov_email_pattern, full_text, re.IGNORECASE)
        gov_emails = [e for e in gov_emails if 'campsable' not in e.lower()]
        
        return {
            'valid': True,
            'paragraphs': paragraph_count,
            'tables': table_count,
            'characters': char_count,
            'has_emojis': has_emojis,
            'gov_emails_found': len(gov_emails),
            'file_size': os.path.getsize(docx_path)
        }
    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 3:
        print("Usage: python doc_converter.py <input.md> <output.docx> [reference.docx]")
        sys.exit(1)
    
    input_md = sys.argv[1]
    output_docx = sys.argv[2]
    reference_docx = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not os.path.exists(input_md):
        print(f"Error: Input file not found: {input_md}")
        sys.exit(1)
    
    with open(input_md, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    success = convert_md_to_docx(markdown_content, output_docx, reference_docx)
    
    if success:
        print(f"✓ Conversion successful: {output_docx}")
        
        # Validate
        quality = validate_docx_quality(output_docx)
        print(f"\nQuality Metrics:")
        print(f"  Paragraphs: {quality['paragraphs']}")
        print(f"  Tables: {quality['tables']}")
        print(f"  Characters: {quality['characters']}")
        print(f"  Emojis: {'✓' if quality['has_emojis'] else '✗'}")
        print(f"  Gov Emails: {'✗ ' + str(quality['gov_emails_found']) if quality['gov_emails_found'] else '✓ 0'}")
        print(f"  File Size: {quality['file_size']:,} bytes")
        
        sys.exit(0)
    else:
        print(f"✗ Conversion failed")
        sys.exit(1)
