import os
import logging
try:
    import pypandoc
except ImportError:
    try:
        # Sometimes it installs as pypandoc_binary but exposes pypandoc
        import pypandoc_binary as pypandoc
    except ImportError:
        pypandoc = None

logger = logging.getLogger(__name__)

def convert_md_to_docx(markdown_content: str, output_path: str):
    """
    Converts Markdown content to a DOCX file using pypandoc.
    Includes pre-processing to clean artifacts and validation.
    
    Args:
        markdown_content (str): The raw markdown string.
        output_path (str): Valid destination path ending in .docx.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    if not pypandoc:
        logger.error("pypandoc module not found. Please run: pip install pypandoc-binary")
        return False

    try:
        # Pre-processing: Clean Markdown
        # Remove bold formatting as requested (double asterisks)
        cleaned_content = markdown_content.replace("**", "")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Convert
        # Using 'gfm' (GitHub Flavored Markdown) as input format handles tables/emojis better usually
        pypandoc.convert_text(
            cleaned_content,
            'docx',
            format='gfm',
            outputfile=output_path,
            extra_args=['--reference-doc=reference.docx'] if os.path.exists('reference.docx') else []
        )
        
        # Validation
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Successfully converted RFQ to DOCX: {output_path}")
            return True
        else:
            logger.error(f"Conversion failed: Output file missing or empty: {output_path}")
            return False
            
    except OSError as e:
        logger.error(f"Pandoc not found or OS error: {e}. Ensure pandoc is installed or use pypandoc-binary.")
        return False
    except Exception as e:
        logger.error(f"Failed to convert MD to DOCX: {e}")
        return False

if __name__ == "__main__":
    # Test block
    logging.basicConfig(level=logging.INFO)
    test_md = """
    # Test RFQ
    
    Dear Vendor:
    
    This is a **test** of the conversion.
    
    | Item | Qty |
    |---|---|
    | Widget | 10 |
    """
    print("Testing DOCX conversion...")
    success = convert_md_to_docx(test_md, "test_output.docx")
    print(f"Conversion Success: {success}")
