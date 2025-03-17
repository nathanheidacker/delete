from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from typing import Union
import tempfile
from marker.output import text_from_rendered
import fitz
import json
from marker.output import json_to_html
import fitz
import io
from typing import Dict, Any, List
import json
from openai import OpenAI
import os
from bs4 import BeautifulSoup
import bs4
import uuid
# Global converter instance - will be initialized on first use
_converter: PdfConverter | None = None

def create_text_content_with_marks(text: str, element=None, preserve_whitespace: bool = False) -> List[Dict[str, Any]]:
    """
    Create text content with marks, preserving meaningful whitespace.
    
    Args:
        text (str): The text content
        element (Optional[Tag]): The element containing the text
        preserve_whitespace (bool): Whether to preserve all whitespace (for code blocks)
        
    Returns:
        List[Dict[str, Any]]: List of text nodes with marks
    """
    # For code blocks, preserve all whitespace
    if preserve_whitespace:
        if not text:
            text = " "
    else:
        # Only collapse multiple spaces into single space, but preserve single spaces
        text = ' '.join(text.split())
        if not text:
            text = " "
    
    # Initialize marks list
    marks = []
    
    # Handle inline formatting elements
    if element:
        # Check for span marks
        if element.name == 'span' and element.get('data-marks'):
            try:
                marks = json.loads(element['data-marks'])
            except:
                pass
        
        # Handle bold
        if element.name == 'b':
            marks.append({"type": "bold"})
        
        # Handle italic
        if element.name == 'i':
            marks.append({"type": "italic"})
        
        # Handle superscript
        if element.name == 'sup':
            marks.append({"type": "superscript"})
    
    return [{
        "type": "text",
        "text": text,
        "marks": marks
    }]

def process_inline_content(element) -> List[Dict[str, Any]]:
    """
    Process inline content recursively, handling nested text and formatting.
    
    Args:
        element: BeautifulSoup element to process
        
    Returns:
        List[Dict[str, Any]]: List of text nodes with marks
    """
    content = []
    
    # Handle text nodes
    if isinstance(element, str):
        # Preserve the space if it's just a space character
        if element.isspace():
            content.extend(create_text_content_with_marks(" "))
        else:
            text = element
            if text:
                content.extend(create_text_content_with_marks(text))
        return content
    
    # Skip comment nodes
    if isinstance(element, bs4.Comment):
        return content
    
    # Handle elements with children
    if hasattr(element, 'children'):
        # Special case for math elements - treat as a single unit
        if element.name == 'math':
            formula = element.get_text().strip()
            if formula:
                return [{
                    "type": "math",
                    "attrs": {"formula": formula}
                }]
        
        # Process each child
        last_was_inline = False  # Track if last element was inline formatting
        for child in element.children:
            if isinstance(child, (str, bs4.Tag)):
                is_inline = isinstance(child, str) or child.name in ['span', 'b', 'i', 'sup']
                
                # Add space between adjacent inline elements if needed
                if last_was_inline and is_inline and content and not child.string.startswith(' '):
                    # Check if there's natural whitespace
                    prev_text = content[-1].get('text', '').strip()
                    curr_text = child.string.strip() if isinstance(child, str) else child.get_text().strip()
                    if prev_text and curr_text and not content[-1]['text'].endswith(' '):
                        content.extend(create_text_content_with_marks(" "))
                
                # Process the element
                if is_inline:
                    text = child.string if isinstance(child, str) else child.get_text()
                    if text:
                        content.extend(create_text_content_with_marks(text, child if isinstance(child, bs4.Tag) else None))
                else:
                    # Recursively process other elements
                    content.extend(process_inline_content(child))
                
                last_was_inline = is_inline
    
    return content

def process_list_item(li_element) -> List[Dict[str, Any]]:
    """
    Process a list item element recursively, handling both text content and nested lists.
    
    Args:
        li_element: BeautifulSoup list item element to process
        
    Returns:
        List[Dict[str, Any]]: List of nodes (paragraph and nested lists)
    """
    content = []
    
    # First, collect all direct text/inline content until we hit a nested list
    current_content = []
    nested_lists = []
    
    for child in li_element.children:
        if isinstance(child, bs4.Tag) and child.name == 'ul':
            # If we have accumulated text content, add it as a paragraph
            if current_content:
                content.append({
                    "type": "paragraph",
                    "content": current_content
                })
                current_content = []
            # Process the nested list
            nested_list = create_node_from_element_with_marks(child)
            if nested_list:
                content.append(nested_list)
        else:
            # Process inline content
            current_content.extend(process_inline_content(child))
    
    # Add any remaining text content as a paragraph
    if current_content:
        content.append({
            "type": "paragraph",
            "content": current_content
        })
    
    return content

def create_node_from_element_with_marks(element) -> Dict[str, Any]:
    """
    Create a node from an element, handling nested content recursively.
    
    Args:
        element: BeautifulSoup element to convert
        
    Returns:
        Dict[str, Any]: Node in ProseMirror format
    """
    if not isinstance(element, bs4.Tag):
        return None
    
    # Get existing node ID or generate a new one
    node_id = element.get('data-node-id') or str(uuid.uuid4())
    
    # Handle headings
    if element.name in ['h1', 'h2', 'h3', 'h4']:
        content = process_inline_content(element)
        if content:
            return {
                "type": "heading",
                "attrs": {
                    "level": int(element.name[1]),
                    "id": node_id
                },
                "content": content
            }
        return None
    
    # Handle paragraphs
    elif element.name == 'p':
        # Check for special block types
        block_type = element.get('block-type')
        if block_type == 'Equation':
            # Find the math element and process it
            math_elem = element.find('math')
            if math_elem:
                formula = math_elem.get_text().strip()
                if formula:
                    return {
                        "type": "math",
                        "attrs": {
                            "formula": formula,
                            "id": node_id
                        }
                    }
        elif block_type == 'ListGroup':
            # Process the list inside the paragraph
            ul_elem = element.find('ul')
            if ul_elem:
                return create_node_from_element_with_marks(ul_elem)
        
        # Regular paragraph processing
        content = process_inline_content(element)
        if content:
            return {
                "type": "paragraph",
                "attrs": {"id": node_id},
                "content": content
            }
        return None
    
    # Handle lists
    elif element.name == 'ul':
        items = []
        for li in element.find_all('li', recursive=False):
            li_content = process_list_item(li)
            if li_content:
                items.append({
                    "type": "listItem",
                    "attrs": {"id": str(uuid.uuid4())},
                    "content": li_content
                })
        if items:
            return {
                "type": "bulletList",
                "attrs": {"id": node_id},
                "content": items
            }
        return None
    
    # Handle code blocks
    elif element.name == 'pre' or element.name == 'code':
        code_text = element.get_text()  # Don't strip whitespace
        if not code_text:
            return None
        language = element.get('class', [''])[0].replace('language-', '') if element.get('class') else ''
        return {
            "type": "codeBlock",
            "attrs": {
                "language": language,
                "id": node_id
            },
            "content": create_text_content_with_marks(code_text, preserve_whitespace=True)
        }
    
    # Handle math blocks
    elif (element.name == 'div' and element.get('data-type') == 'math') or element.name == 'math':
        formula = element.get('data-formula', '').strip() or element.get_text().strip()
        if not formula:
            return None
        return {
            "type": "math",
            "attrs": {
                "formula": formula,
                "id": node_id
            }
        }
    
    # Handle blockquotes
    elif element.name == 'blockquote':
        content = []
        for child in element.children:
            if isinstance(child, bs4.Tag):
                child_node = create_node_from_element_with_marks(child)
                if child_node:
                    content.append(child_node)
        if content:
            return {
                "type": "blockquote",
                "attrs": {"id": node_id},
                "content": content
            }
        return None
    
    # Handle tables
    elif element.name in ['table', 'tbody']:
        rows = []
        for tr in element.find_all('tr', recursive=False):
            cells = []
            for td in tr.find_all(['td', 'th'], recursive=False):
                cell_type = "tableHeader" if td.name == 'th' else "tableCell"
                cell_content = process_inline_content(td)
                if not cell_content:
                    cell_content = create_text_content_with_marks(" ")
                cells.append({
                    "type": cell_type,
                    "attrs": {"id": str(uuid.uuid4())},
                    "content": [{
                        "type": "paragraph",
                        "attrs": {"id": str(uuid.uuid4())},
                        "content": cell_content
                    }]
                })
            
            if cells:
                rows.append({
                    "type": "tableRow",
                    "attrs": {"id": str(uuid.uuid4())},
                    "content": cells
                })
        
        if rows:
            return {
                "type": "table",
                "attrs": {"id": node_id},
                "content": rows
            }
    
    return None

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

def pdf_to_tiptap(pdf_bytes: bytes) -> str:
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

    html = ""
    for block in rendered.children:
        html += json_to_html(block)

    # Parse the HTML
    soup = BeautifulSoup(html, 'html.parser')
    
    # Convert to final document
    doc = {"type": "doc", "content": []}
    content_root = soup.find('body') or soup
    stack = [content_root]
    
    while stack:
        element = stack.pop()
        
        if element.name is None or isinstance(element, (str, bs4.Comment)):
            continue
            
        node = create_node_from_element_with_marks(element)
        if node is not None:
            doc["content"].append(node)
            continue
            
        for child in reversed(list(element.children)):
            if child.name is not None:
                stack.append(child)
    
    return doc


if __name__ == "__main__":
    with open("test.pdf", "rb") as f:
        pdf_bytes = f.read()
    print(pdf_to_tiptap(pdf_bytes))