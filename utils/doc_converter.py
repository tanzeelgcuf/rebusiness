"""
Professional RFQ DOCX Builder
Creates polished, template-compliant DOCX files matching Claude Vendor/Service List style
"""
import os
import re
import logging
from typing import Optional, List, Dict
from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

logger = logging.getLogger(__name__)


class ProfessionalRFQBuilder:
    """
    Builds professional RFQ documents with exact template compliance.
    Matches Claude Vendor List.odt and Claude Service List.odt styling.
    """
    
    def __init__(self):
        self.doc = Document()
        self._setup_styles()
        self._setup_page_margins()
    
    def _setup_page_margins(self):
        """Set professional page margins."""
        sections = self.doc.sections
        for section in sections:
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)
    
    def _setup_styles(self):
        """Create custom styles matching reference templates."""
        styles = self.doc.styles
        
        # Main Heading Style (H1 with emoji)
        try:
            h1_style = styles['Heading 1']
        except KeyError:
            h1_style = styles.add_style('Heading 1', WD_STYLE_TYPE.PARAGRAPH)
        
        h1_style.font.size = Pt(16)
        h1_style.font.bold = True
        h1_style.font.color.rgb = RGBColor(0, 0, 0)
        h1_style.font.name = 'Calibri'
        h1_style.paragraph_format.space_before = Pt(12)
        h1_style.paragraph_format.space_after = Pt(6)
        h1_style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        
        # Section Heading Style (H2 with emoji)
        try:
            h2_style = styles['Heading 2']
        except KeyError:
            h2_style = styles.add_style('Heading 2', WD_STYLE_TYPE.PARAGRAPH)
        
        h2_style.font.size = Pt(13)
        h2_style.font.bold = True
        h2_style.font.color.rgb = RGBColor(0, 0, 139)  # Dark blue
        h2_style.font.name = 'Calibri'
        h2_style.paragraph_format.space_before = Pt(12)
        h2_style.paragraph_format.space_after = Pt(3)
        
        # Normal text
        normal_style = styles['Normal']
        normal_style.font.size = Pt(11)
        normal_style.font.name = 'Calibri'
        normal_style.paragraph_format.space_after = Pt(6)
        normal_style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        
        # Bullet list style
        try:
            bullet_style = styles['List Bullet']
        except KeyError:
            bullet_style = styles.add_style('List Bullet', WD_STYLE_TYPE.PARAGRAPH)
        
        bullet_style.font.size = Pt(11)
        bullet_style.font.name = 'Calibri'
        bullet_style.paragraph_format.left_indent = Inches(0.25)
        bullet_style.paragraph_format.space_after = Pt(3)
    
    def parse_and_build(self, markdown_content: str):
        """
        Parse markdown and build professional document.
        """
        # Clean content first
        markdown_content = self._clean_markdown(markdown_content)
        
        lines = markdown_content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Skip empty lines
            if not line.strip():
                i += 1
                continue
            
            # Handle different content types
            if line.startswith('# '):
                # Main title (H1)
                self._add_title(line[2:].strip())
            
            elif line.startswith('## '):
                # Section heading (H2 with emoji)
                self._add_section_heading(line[3:].strip())
            
            elif line.startswith('### '):
                # Subsection (H3)
                self._add_subsection(line[4:].strip())
            
            elif line.startswith('---'):
                # Horizontal rule
                self._add_separator()
            
            elif line.strip().startswith('|') and '|' in line:
                # Table detected
                table_lines = []
                while i < len(lines) and '|' in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                self._add_table(table_lines)
                continue
            
            elif re.match(r'^- \[ \]', line.strip()):
                # Checkbox (for SERVICE)
                self._add_checkbox_item(line.strip()[6:])
            
            elif line.strip().startswith('- '):
                # Regular bullet
                self._add_bullet(line.strip()[2:])
            
            elif re.match(r'^\d+\.\s', line.strip()):
                # Numbered list
                self._add_numbered_item(line.strip())
            
            else:
                # Regular paragraph
                self._add_paragraph(line.strip())
            
            i += 1
    
    def _clean_markdown(self, content: str) -> str:
        """Remove markdown artifacts and clean content."""
        # Remove HTML comments
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)
        
        # Remove bold markers
        content = content.replace('**', '')
        
        # Replace government emails
        content = re.sub(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(?:gov|mil)\b',
            'bobbysmitty078@gmail.com',
            content,
            flags=re.IGNORECASE
        )
        
        # Normalize whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content
    
    def _add_title(self, text: str):
        """Add main title (H1) - centered and bold."""
        p = self.doc.add_heading(text, level=1)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Make it larger
        for run in p.runs:
            run.font.size = Pt(18)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0, 0, 0)
    
    def _add_section_heading(self, text: str):
        """Add section heading (H2) with emoji support."""
        p = self.doc.add_heading(text, level=2)
        
        # Style the heading
        for run in p.runs:
            run.font.size = Pt(13)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0, 0, 139)  # Dark blue
    
    def _add_subsection(self, text: str):
        """Add subsection heading (H3)."""
        p = self.doc.add_heading(text, level=3)
        
        for run in p.runs:
            run.font.size = Pt(12)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0, 0, 0)
    
    def _add_paragraph(self, text: str):
        """Add normal paragraph with proper spacing."""
        if not text.strip():
            return
        
        p = self.doc.add_paragraph(text)
        p.style = 'Normal'
        
        # Ensure consistent formatting
        for run in p.runs:
            run.font.size = Pt(11)
            run.font.name = 'Calibri'
    
    def _add_bullet(self, text: str):
        """Add bullet point."""
        p = self.doc.add_paragraph(text, style='List Bullet')
        
        for run in p.runs:
            run.font.size = Pt(11)
    
    def _add_checkbox_item(self, text: str):
        """Add checkbox item (for SERVICE RFQs)."""
        # Use ballot box emoji
        p = self.doc.add_paragraph('☐ ' + text, style='List Bullet')
        
        for run in p.runs:
            run.font.size = Pt(11)
    
    def _add_numbered_item(self, text: str):
        """Add numbered list item."""
        # Extract number and text
        match = re.match(r'^(\d+)\.\s+(.+)$', text)
        if match:
            num, content = match.groups()
            p = self.doc.add_paragraph(content, style='List Number')
        else:
            p = self.doc.add_paragraph(text, style='List Number')
        
        for run in p.runs:
            run.font.size = Pt(11)
    
    def _add_table(self, table_lines: List[str]):
        """
        Add professional table with proper styling.
        Matches template table appearance.
        """
        if not table_lines:
            return
        
        # Parse rows
        rows = []
        for line in table_lines:
            # Skip separator lines
            if re.match(r'^\|[\s\-:]+\|$', line):
                continue
            
            # Split and clean cells
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if cells:
                rows.append(cells)
        
        if not rows:
            return
        
        # Determine column count
        max_cols = max(len(row) for row in rows)
        
        # Create table
        table = self.doc.add_table(rows=len(rows), cols=max_cols)
        
        # Apply professional styling
        table.style = 'Light Grid Accent 1'  # Professional table style
        
        # Set column widths for readability
        total_width = Inches(6.5)  # Page width minus margins
        col_width = total_width / max_cols
        
        for row in table.rows:
            for cell in row.cells:
                cell.width = col_width
        
        # Populate cells
        for i, row_data in enumerate(rows):
            row = table.rows[i]
            for j, cell_data in enumerate(row_data):
                if j < len(row.cells):
                    cell = row.cells[j]
                    cell.text = cell_data
                    
                    # Format cell text
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.size = Pt(10)
                            run.font.name = 'Calibri'
                            
                            # Header row styling
                            if i == 0:
                                run.font.bold = True
                                run.font.color.rgb = RGBColor(255, 255, 255)
                                # Add background color to header (Dark Blue)
                                self._set_cell_background(cell, "4472C4")
                            else:
                                run.font.bold = False
                        
                        # Center align header
                        if i == 0:
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add spacing after table
        self.doc.add_paragraph()
    
    def _set_cell_background(self, cell, hex_color: str):
        """Set cell background color."""
        shading_elm = OxmlElement('w:shd')
        shading_elm.set(qn('w:fill'), hex_color)
        cell._element.get_or_add_tcPr().append(shading_elm)
    
    def _add_separator(self):
        """Add horizontal separator line."""
        p = self.doc.add_paragraph()
        p.paragraph_format.border_bottom = True
        p.paragraph_format.space_after = Pt(6)
    
    def save(self, output_path: str):
        """Save document to file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        self.doc.save(output_path)
        logger.info(f"Professional DOCX saved: {output_path}")


def convert_md_to_professional_docx(markdown_content: str, output_path: str) -> bool:
    """
    Convert markdown to professional DOCX with template styling.
    
    Args:
        markdown_content: Raw markdown RFQ content
        output_path: Destination .docx file
    
    Returns:
        True if successful
    """
    try:
        builder = ProfessionalRFQBuilder()
        builder.parse_and_build(markdown_content)
        builder.save(output_path)
        
        # Verify output
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        else:
            logger.error("Output file empty or not created")
            return False
            
    except Exception as e:
        logger.error(f"Professional DOCX conversion failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# Make this the default export
convert_md_to_docx = convert_md_to_professional_docx


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 3:
        print("Usage: python doc_converter.py <input.md> <output.docx>")
        sys.exit(1)
    
    input_md = sys.argv[1]
    output_docx = sys.argv[2]
    
    if not os.path.exists(input_md):
        print(f"Error: {input_md} not found")
        sys.exit(1)
    
    with open(input_md, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if convert_md_to_professional_docx(content, output_docx):
        print(f"✓ Professional DOCX created: {output_docx}")
        print(f"  Size: {os.path.getsize(output_docx):,} bytes")
    else:
        print("✗ Conversion failed")
        sys.exit(1)