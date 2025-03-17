from __future__ import annotations

import json
import tempfile
from typing import Any, Literal
from uuid import uuid4

import bs4
import fitz
from bs4.element import PageElement, NavigableString, Tag
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import json_to_html
from openai import OpenAI
from pydantic import BaseModel

ProseMirrorNodeTypeString = Literal[
    "math",
    "paragraph",
    "heading",
    "listItem",
    "bulletList",
    "doc",
    "codeBlock",
    "blockQuote",
    "tableRow",
    "tableHeader",
    "tableCell",
    "table",
    "image",
    "text",
]


ProseMirrorMarkTypeString = Literal[
    "bold", "italic", "superscript", "color", "strikethrough"
]


class ProseMirrorNode(BaseModel):
    type: ProseMirrorNodeTypeString
    attrs: dict[str, Any] = {}
    content: list[ProseMirrorNode] = []
    marks: list[ProseMirrorMark] = []


class ProseMirrorMark(BaseModel):
    type: ProseMirrorMarkTypeString


_converter = None


def _get_converter() -> PdfConverter:
    global _converter
    if _converter is None:
        _converter = PdfConverter(
            artifact_dict=create_model_dict(),
            renderer="marker.renderers.json.JSONRenderer",
        )
    return _converter


NODE_TYPE_MAP = {
    "h1": "heading",
    "h2": "heading",
    "h3": "heading",
    "h4": "heading",
    "tbody": "table",
    "tr": "tableRow",
    "th": "tableHeader",
    "td": "tableCell",
    "img": "image",
    "ul": "bulletList",
    "listGroup": "bulletList",
    "li": "listItem",
    "blockquote": "blockQuote",
    "Equation": "math",
    "Text": "text",
}


def get_node_type(element: PageElement) -> ProseMirrorNodeTypeString | None:
    if isinstance(element, NavigableString):
        return "text"
    node_type = element.name
    block_type = element.get("block_type")
    return None


def convert_recursive(element: PageElement | str) -> ProseMirrorNode:
    if isinstance(element, NavigableString):
        return ProseMirrorNode(
            type="text", content=[convert_recursive(e) for e in element.children]
        )
    node_type = get_node_type(element)
    marks = []
    attrs = {"id": str(uuid4())}
    if node_type == "text":
        if element.name == "b":
            marks.append({"type": "bold"})
        elif element.name == "i":
            marks.append({"type": "italic"})
        elif element.name == "sup":
            marks.append({"type": "superscript"})
    elif node_type == "math":
        formula = element.find("math").get_text().strip()
        attrs["formula"] = formula
    elif node_type == "codeBlock":
        code = element.get_text()
        language = element.get("class", [""])[0].replace("language-", "")


def create_text_node(
    element: PageElement | str, marks: list[ProseMirrorMark] = []
) -> ProseMirrorNode:
    marks = []
    text = element
    if isinstance(element, bs4.Tag):
        text = element.text
        if element.name == "b":
            marks.append({"type": "bold"})
        elif element.name == "i":
            marks.append({"type": "italic"})
        elif element.name == "sup":
            marks.append({"type": "superscript"})
    return ProseMirrorNode(type="text", content=text, marks=marks)


def process_inline_content(element: PageElement) -> list[ProseMirrorNode]:
    return [create_text_node(child) for child in element.children]


def create_heading_node(element: PageElement) -> ProseMirrorNode:
    content = process_inline_content(element)
    if content:
        return ProseMirrorNode(
            type="heading", attrs={"level": int(element.name[1])}, content=content
        )
    return None


def create_list_node(element: PageElement | str) -> ProseMirrorNode:
    if isinstance(element, str):
        return create_text_node(element)
    node_type = element.name


def create_list_node(element: PageElement) -> ProseMirrorNode:
    items = []
    for li in element.find_all("li", recursive=False):
        li_content = process_list_item(li)
        if li_content:
            items.append(
                {
                    "type": "listItem",
                    "attrs": {"id": str(uuid.uuid4())},
                    "content": li_content,
                }
            )
    if items:
        return {"type": "bulletList", "attrs": {"id": node_id}, "content": items}
    return None


def create_blockquote_node(element: PageElement) -> ProseMirrorNode: ...


def create_table_node(element: PageElement) -> ProseMirrorNode: ...


def create_code_node(element: PageElement) -> ProseMirrorNode: ...


def create_equation_node(element: PageElement) -> ProseMirrorNode: ...


def create_image_node(element: PageElement) -> ProseMirrorNode: ...


node_function_map = {
    "h1": create_heading_node,
    "h2": create_heading_node,
    "h3": create_heading_node,
    "h4": create_heading_node,
    "img": create_image_node,
    "blockquote": create_blockquote_node,
    "table": create_table_node,
    "pre": create_code_node,
    "code": create_code_node,
    "Equation": create_equation_node,
    "Text": create_text_node,
    "ListGroup": create_list_node,
}


def create_node(element: PageElement) -> ProseMirrorNode:
    node = None
    if not isinstance(element, bs4.Tag):
        return node

    node_type = element.name
    if node_type == "p":
        node_type = element.get("block-type")
    node = node_function_map.get(node_type, lambda e: None)(element)

    if node:
        node.attrs = node.attrs | {"id": str(uuid4())}
    return node


def convert_pdf(pdf: bytes) -> dict:
    converter = _get_converter()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
        temp_file.write(pdf)
        temp_file.flush()
        rendered = converter(temp_file.name)
    html = ""
    sentinel = "$$PAGEBREAK"
    for block in rendered.children:
        html += json_to_html(block) + f"<div>{sentinel}</div>"

    soup = bs4.BeautifulSoup(html, "html.parser")

    # Convert to final document
    doc = {"type": "doc", "content": []}
    stack = list(soup.children)[::-1]

    while stack:
        element = stack.pop()

        if element.name is None or isinstance(element, (str, bs4.Comment)):
            continue

        node = create_node(element)
        if node is not None:
            doc["content"].append(node)
            continue

        stack.extend(list(element.children)[::-1])

    return doc


if __name__ == "__main__":
    with open("test.pdf", "rb") as f:
        pdf = f.read()
    print(convert_pdf(pdf))
