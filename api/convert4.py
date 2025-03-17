import fitz
import io
from typing import Dict, Any, List
import json
from openai import OpenAI
import os
from bs4 import BeautifulSoup
import bs4

oai = OpenAI(base_url="https://gateway.ai.cloudflare.com/v1/f0d60d63e373ab194adfb2a3ab113aad/genesis/openai")

def extract_text_with_formatting(page: fitz.Page) -> List[Dict[str, Any]]:
    """
    Extracts text blocks from a PDF page while preserving basic formatting.
    Returns a list of text blocks with their formatting information.
    """
    blocks = []
    for block in page.get_text("dict")["blocks"]:
        if "lines" not in block:
            continue
            
        for line in block["lines"]:
            for span in line["spans"]:
                # Get background color if available
                bgcolor = None
                try:
                    # Extract color info from the span's background
                    colorspace = span.get("colorspace", -1)
                    if colorspace >= 0:  # Has color information
                        bgcolor = span.get("bgcolor", (1, 1, 1))  # Default to white if not specified
                except:
                    bgcolor = (1, 1, 1)  # Default to white on error
                
                text_block = {
                    "text": span["text"],
                    "font": span["font"],
                    "size": span["size"],
                    "flags": span["flags"],  # Contains bold, italic info
                    "color": span["color"],
                    "bgcolor": bgcolor
                }
                blocks.append(text_block)
    
    return blocks

def determine_text_style(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determines text styling based on PDF text properties.
    Returns a dictionary of style attributes and marks to apply.
    """
    flags = block["flags"]
    font_lower = block["font"].lower()
    color = block["color"]
    
    # Initialize marks array for text formatting
    marks = []
    
    # Handle bold (16 is the bold flag in PyMuPDF)
    if bool(flags & 16) or "bold" in font_lower:
        marks.append({"type": "bold"})
    
    # Handle italic (1 is the italic flag in PyMuPDF)
    if bool(flags & 1) or "italic" in font_lower:
        marks.append({"type": "italic"})
    
    # Handle underline (8 is the underline flag in PyMuPDF)
    if bool(flags & 8):
        marks.append({"type": "underline"})
    
    # Handle strike-through (64 is the strike-through flag in PyMuPDF)
    if bool(flags & 64):
        marks.append({"type": "strike"})
    
    # Handle text color if it's not black
    if color:
        # Convert integer color to RGB if necessary
        if isinstance(color, int):
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
        else:
            # Assume it's a tuple of RGB values
            r, g, b = color

        # Only add color if it's not black
        if (r, g, b) != (0, 0, 0):
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            marks.append({
                "type": "textStyle",
                "attrs": {"color": hex_color}
            })
    
    # Handle highlight if background color is present
    bgcolor = block.get("bgcolor", None)
    if bgcolor:
        # Convert integer color to RGB if necessary
        if isinstance(bgcolor, int):
            r = (bgcolor >> 16) & 0xFF
            g = (bgcolor >> 8) & 0xFF
            b = bgcolor & 0xFF
            # Convert to 0-1 range for consistency with tuple format
            r, g, b = r/255, g/255, b/255
        else:
            # Assume it's a tuple of RGB values in 0-1 range
            r, g, b = bgcolor

        # Only add highlight if it's not white
        if (r, g, b) != (1, 1, 1):
            hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            marks.append({
                "type": "highlight",
                "attrs": {"color": hex_color}
            })
    
    return {
        "heading": block["size"] >= 14,  # Assume larger text is a heading
        "marks": [mark for mark in marks if mark is not None]
    }

def pdf_to_tiptap(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Converts a PDF document to a Tiptap/ProseMirror compatible schema.
    
    Args:
        pdf_bytes (bytes): The PDF file content as bytes
        
    Returns:
        Dict[str, Any]: A ProseMirror compatible document schema
    """
    # Open PDF from bytes
    pdf_stream = io.BytesIO(pdf_bytes)
    doc = fitz.open(stream=pdf_stream, filetype="pdf")
    
    # Extract text with formatting from all pages
    all_blocks = []
    for page in doc:
        blocks = extract_text_with_formatting(page)
        all_blocks.extend(blocks)
    
    # Create a mapping of text to its formatting information
    format_map = {}
    text_content = ""
    
    for block in all_blocks:
        text = block["text"].strip()
        if text:
            format_map[text] = determine_text_style(block)
            text_content += text + "\n"
    
    # Use LLM to enhance structure
    html_content = enhance_structure_with_llm(text_content)
    
    # Parse the HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Function to process text nodes and add formatting
    def process_text_nodes(element):
        if isinstance(element, str):
            text = element.strip()
            if text:
                # Find all formatted texts that appear in this text node
                replacements = []
                for fmt_text, fmt_info in format_map.items():
                    if fmt_text in text:
                        # Create a new span with the formatting information
                        new_span = soup.new_tag('span')
                        new_span['data-marks'] = json.dumps(fmt_info["marks"])
                        new_span.string = fmt_text
                        # Keep track of where this text appears and its replacement
                        start = text.index(fmt_text)
                        replacements.append((start, fmt_text, new_span))
                
                if replacements:
                    # Sort replacements by position (to handle overlapping matches)
                    replacements.sort(key=lambda x: x[0])
                    # Create a new NavigableString for the remaining text
                    current_pos = 0
                    parent = element.parent
                    for start, fmt_text, span in replacements:
                        # Add any text before this match
                        if start > current_pos:
                            parent.insert(parent.index(element), soup.new_string(text[current_pos:start]))
                        # Add the formatted span
                        parent.insert(parent.index(element), span)
                        current_pos = start + len(fmt_text)
                    # Add any remaining text
                    if current_pos < len(text):
                        parent.insert(parent.index(element), soup.new_string(text[current_pos:]))
                    # Remove the original element
                    element.replace_with('')
        else:
            for child in list(element.children):
                process_text_nodes(child)
    
    # Process all text nodes in the HTML
    process_text_nodes(soup)
    
    # Convert to ProseMirror schema with formatting
    def create_text_content_with_marks(text: str, element=None) -> List[Dict[str, Any]]:
        text = text.strip()
        if not text:
            text = " "
        
        # Check if text has associated marks from a span
        marks = []
        if element and element.name == 'span' and element.get('data-marks'):
            try:
                marks = json.loads(element['data-marks'])
            except:
                pass
        
        return [{
            "type": "text",
            "text": text,
            "marks": marks
        }]
    
    # Update create_node_from_element to use the new text content function
    def create_node_from_element_with_marks(element) -> Dict[str, Any]:
        if element.name == 'h1':
            text = element.get_text().strip()
            if not text:
                return None
            return {
                "type": "heading",
                "attrs": {"level": 1},
                "content": create_text_content_with_marks(text, element.find('span'))
            }
        elif element.name == 'h2':
            text = element.get_text().strip()
            if not text:
                return None
            return {
                "type": "heading",
                "attrs": {"level": 2},
                "content": create_text_content_with_marks(text, element.find('span'))
            }
        elif element.name == 'p':
            spans = element.find_all('span') or [element]
            content = []
            for span in spans:
                text = span.get_text().strip()
                if text:
                    content.extend(create_text_content_with_marks(text, span))
            if not content:
                content = create_text_content_with_marks(" ")
            return {
                "type": "paragraph",
                "content": content
            }
        elif element.name == 'ul':
            items = []
            for li in element.find_all('li', recursive=False):
                text = li.get_text().strip()
                if text:  # Only add non-empty list items
                    items.append({
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": create_text_content_with_marks(text)
                            }
                        ]
                    })
            if items:  # Only create list if there are non-empty items
                return {
                    "type": "bulletList",
                    "content": items
                }
            return None
        elif element.name == 'ol':
            items = []
            for li in element.find_all('li', recursive=False):
                text = li.get_text().strip()
                if text:  # Only add non-empty list items
                    items.append({
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": create_text_content_with_marks(text)
                            }
                        ]
                    })
            if items:  # Only create list if there are non-empty items
                return {
                    "type": "orderedList",
                    "content": items
                }
            return None
        elif element.name == 'pre' or element.name == 'code':
            # Handle code blocks
            code_text = element.get_text().strip()
            if not code_text:
                return None
            language = element.get('class', [''])[0].replace('language-', '') if element.get('class') else ''
            return {
                "type": "codeBlock",
                "attrs": {"language": language},
                "content": create_text_content_with_marks(code_text)
            }
        elif element.name == 'div' and element.get('data-type') == 'math':
            # Handle LaTeX math blocks
            formula = element.get('data-formula', '').strip()
            if not formula:
                return None
            return {
                "type": "math",
                "attrs": {"formula": formula}
            }
        elif element.name == 'img':
            # Handle images
            src = element.get('src', '').strip()
            if not src:  # Don't create image nodes without source
                return None
            return {
                "type": "image",
                "attrs": {
                    "src": src,
                    "alt": element.get('alt', '').strip(),
                    "title": element.get('title', '').strip()
                }
            }
        elif element.name == 'table':
            # Handle tables
            rows = []
            for tr in element.find_all('tr', recursive=False):
                cells = []
                for td in tr.find_all(['td', 'th'], recursive=False):
                    cell_type = "tableHeader" if td.name == 'th' else "tableCell"
                    text = td.get_text().strip()
                    if not text:
                        text = " "  # Ensure table cells always have at least a space
                    cells.append({
                        "type": cell_type,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": create_text_content_with_marks(text)
                            }
                        ]
                    })
                
                if cells:
                    rows.append({
                        "type": "tableRow",
                        "content": cells
                    })
            
            if rows:
                return {
                    "type": "table",
                    "content": rows
                }
        
        return None
    
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

def enhance_structure_with_llm(content: str) -> str:
    """
    Uses OpenAI to enhance the document structure and identify semantic elements.
    """
    
    prompt = """
    Convert this text into semantic HTML, preserving the document structure. 
    Identify headings, paragraphs, lists, tables, code blocks, and math formulas.
    Keep the content exactly the same, but add appropriate HTML tags.
    
    For code blocks, wrap them in <pre><code class="language-xxx">...</code></pre>
    For math formulas, use <div data-type="math" data-formula="...">...</div>
    For tables, use proper <table>, <tr>, <th>, and <td> tags
    
    Text to convert:
    
    {content}
    """.format(content=content)
    
    response = oai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a document structure expert. Convert text to semantic HTML, properly handling code blocks, math formulas, and tables."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
    )
    
    return response.choices[0].message.content


if __name__ == "__main__":
    with open("test.pdf", "rb") as f:
        pdf_bytes = f.read()
    tiptap_doc = pdf_to_tiptap(pdf_bytes)

    print(tiptap_doc)