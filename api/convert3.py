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
            # Get line's bounding box
            line_bbox = line["bbox"]  # [x0, y0, x1, y1]
            
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
                    "bgcolor": bgcolor,
                    "bbox": span["bbox"],  # [x0, y0, x1, y1] for the span
                    "line_bbox": line_bbox,  # [x0, y0, x1, y1] for the entire line
                    "block_bbox": block["bbox"],  # [x0, y0, x1, y1] for the entire block
                    "origin": "line"  # Mark this as coming from a line
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

def is_plain_text(block: Dict[str, Any]) -> bool:
    """
    Determines if a block contains plain text without special formatting.
    
    Args:
        block (Dict[str, Any]): Text block with raw PDF formatting information
        
    Returns:
        bool: True if the block is plain text without special formatting
    """
    style = determine_text_style(block)
    return (
        not style["marks"] and  # No marks (bold, italic, etc.)
        block.get("color") in ((0, 0, 0), 0, None) and  # Black text
        (block.get("bgcolor") is None or block.get("bgcolor") == (1, 1, 1)) and  # White or no background
        not style["heading"]  # Not a heading
    )

def merge_plaintext_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merges consecutive blocks with plain text into a single block.
    
    Args:
        blocks (List[Dict[str, Any]]): List of text blocks with formatting information
        
    Returns:
        List[Dict[str, Any]]: List of merged text blocks where consecutive plain text blocks
                             are combined into single blocks
    """
    if not blocks:
        return []
    
    merged_blocks = []
    current_block = None
    
    for block in blocks:
        if current_block is None:
            current_block = block.copy()
        elif is_plain_text(block) and is_plain_text(current_block):
            # Merge with previous block if both are plain text
            current_block["text"] += " " + block["text"]
        else:
            # Add current block to results and start a new one
            merged_blocks.append(current_block)
            current_block = block.copy()
    
    # Add the last block if it exists
    if current_block is not None:
        merged_blocks.append(current_block)
    
    return merged_blocks


def llm_convert(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Converts PDF blocks into ProseMirror compatible nodes using LLM assistance.
    
    Args:
        blocks (List[Dict[str, Any]]): List of text blocks with formatting information
        
    Returns:
        List[Dict[str, Any]]: List of ProseMirror compatible nodes
    """
    # Prepare the blocks for LLM analysis by converting them to a simpler format
    simplified_blocks = []
    for block in blocks:
        style = determine_text_style(block)
        simplified_block = {
            "text": block["text"],
            "size": block["size"],
            "bbox": block["bbox"],
            "line_bbox": block["line_bbox"],
            "block_bbox": block["block_bbox"],
            "marks": style["marks"],
            "is_heading": style["heading"]
        }
        simplified_blocks.append(simplified_block)
    
    # Create a prompt for the LLM
    prompt = f"""
You are a specialized AI that converts PDF text blocks into ProseMirror compatible document nodes. You must preserve ALL formatting and return only valid JSON that matches the ProseMirror schema exactly.
Given text blocks from a PDF with their formatting and positioning information, convert them into valid ProseMirror nodes.
Each block contains: text content, font size, bounding boxes (bbox) for the text/line/block, and formatting marks.

The output must be a valid ProseMirror document that follows these specifications:

Available Node Types:
1. "doc" - The root node type
2. "paragraph" - Basic text paragraph
3. "text" - Plain text content
4. "heading" - Headers (levels 1-2 only)
5. "bulletList" - Unordered lists
6. "orderedList" - Numbered lists
7. "listItem" - Individual list items
8. "codeBlock" - Code blocks
9. "image" - Image content
10. "table" - Table container
11. "tableRow" - Table rows
12. "tableCell" - Regular table cells
13. "tableHeader" - Header table cells
14. "math" - Mathematical content

Available Mark Types:
1. "bold" - Bold text
2. "italic" - Italic text
3. "strike" - Strikethrough text
4. "underline" - Underlined text
5. "textStyle" - For text color (use with attrs: {{"color": "#hexcode"}})
6. "highlight" - For background color (use with attrs: {{"color": "#hexcode"}})

Conversion Rules:
1. Group text blocks that are semantically related (same paragraph/heading/list)
2. Use bbox information to determine text flow and relationships
3. ALWAYS preserve ALL formatting marks from the input blocks
4. Convert large text (size >= 14) into heading nodes (levels 1-2)
5. Detect and properly format lists based on indentation and positioning
6. Maintain proper document structure with paragraphs
7. Every text node MUST be have a parent block-level node (paragraph, heading, etc.)
8. Color information must be preserved using textStyle marks with hex color codes
9. Background colors must be preserved using highlight marks with hex color codes

Example mark structure:
{{
  "type": "text",
  "text": "Sample text",
  "marks": [
    {{"type": "bold"}},
    {{"type": "textStyle", "attrs": {{"color": "#ff0000"}}}},
    {{"type": "highlight", "attrs": {{"color": "#ffff00"}}}}
  ]
}}

Return only valid JSON representing ProseMirror nodes.""".strip()

    # Call OpenAI API
    try:
        response = oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": prompt
            }, {
                "role": "user",
                "content": json.dumps(simplified_blocks, indent=2)
            }],
            response_format={ "type": "json_object" },
            temperature=0
        )
        
        # Parse the response
        result = json.loads(response.choices[0].message.content)
        
        # Ensure the result has the correct top-level structure
        if not isinstance(result, dict) or "type" not in result:
            result = {
                "type": "doc",
                "content": result if isinstance(result, list) else [result]
            }
        
        return result
        
    except Exception as e:
        print(f"Error in LLM conversion: {e}")
        # Fallback: Convert blocks to simple paragraphs
        return {
            "type": "doc",
            "content": [{
                "type": "paragraph",
                "content": [{
                    "type": "text",
                    "text": block["text"],
                    "marks": determine_text_style(block)["marks"]
                }]
            } for block in blocks]
        }
    
def to_camel_case(string: str) -> str:
    words = string.split('_')
    return words[0] + ''.join(word.capitalize() for word in words[1:])

def convert_to_camel_case(blocks: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively converts all type and mark type keys from snake_case to camelCase in ProseMirror blocks.
    
    Args:
        blocks (Dict[str, Any]): ProseMirror document structure
        
    Returns:
        Dict[str, Any]: Updated ProseMirror structure with camelCase types
    """
    queue = [blocks]
    while queue:
        block = queue.pop(0)
        if isinstance(block, dict):
            block["type"] = to_camel_case(block["type"])
            queue.extend(block.get("content", []))
    return blocks

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
    
    # Convert blocks to ProseMirror format using LLM
    prose_mirror_data = llm_convert(all_blocks)

    # Convert types to camelCase
    prose_mirror_data = convert_to_camel_case(prose_mirror_data)

    return prose_mirror_data

if __name__ == "__main__":
    with open("test.pdf", "rb") as f:
        pdf_bytes = f.read()
    data = pdf_to_tiptap(pdf_bytes)

    print(data)
