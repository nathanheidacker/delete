from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from typing import Union
import tempfile
from marker.output import text_from_rendered
import fitz
import json
# Global converter instance - will be initialized on first use
_converter: PdfConverter | None = None

def _get_converter() -> PdfConverter:
    """
    Get or create the global PDF converter instance.
    
    Returns:
        PdfConverter: The global converter instance
    """
    global _converter
    if _converter is None:
        _converter = PdfConverter(
            artifact_dict=create_model_dict(),
            renderer="marker.renderers.json.JSONRenderer"
        )
    return _converter

def pdf_to_markdown(pdf_bytes: bytes) -> str:
    """
    Convert PDF bytes to HTML string using marker library.
    
    Args:
        pdf_bytes (bytes): The PDF content as bytes
        
    Returns:
        str: The converted HTML string
    """
    # Get the global converter instance
    converter = _get_converter()

    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
        temp_file.write(pdf_bytes)
        temp_file.flush()
        rendered = converter(temp_file.name)
        
    markdown, _, images = text_from_rendered(rendered)
    # The rendered output contains the HTML content
    return markdown

def pdf_to_tiptap(pdf_bytes: bytes) -> str:
    """
    Convert PDF bytes to tiptap JSON using marker library.
    
    Args:
        pdf_bytes (bytes): The PDF content as bytes

    Returns:
        str: The converted tiptap JSON string
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")