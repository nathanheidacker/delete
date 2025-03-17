from __future__ import annotations
from pydantic import BaseModel
from typing import Literal, Any, Union
from bs4.element import PageElement, NavigableString, Tag
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import json_to_html
from bs4 import BeautifulSoup
import tempfile
from uuid import uuid4

# TODO NEED TO HANDLE <a> tag, LINKS

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
    "link",
    "skip",
]

ProseMirrorMarkTypeString = Literal[
    "bold", "italic", "superscript", "color", "strikethrough"
]

PAGE_BREAK_SENTINEL = "$$PAGEBREAK$$"


class ProseMirrorMark(BaseModel):
    type: ProseMirrorMarkTypeString
    attrs: dict[str, Any] = {}


class ProseMirrorTextNode(BaseModel):
    type: Literal["text"] = "text"
    attrs: dict[str, Any] = {}
    text: str
    marks: list[ProseMirrorMark] = []


class ProseMirrorContainerNode(BaseModel):
    type: ProseMirrorNodeTypeString
    attrs: dict[str, Any] = {}
    content: list[ProseMirrorNode] = []
    marks: list[ProseMirrorMark] = []


ProseMirrorNode = Union[ProseMirrorTextNode, ProseMirrorContainerNode]
# Necessary for self-referencing models
ProseMirrorContainerNode.model_rebuild()

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
    "b": "text",
    "i": "text",
    "a": "link",
}


def get_node_type(element: Tag) -> ProseMirrorNodeTypeString:
    block_type = element.get("block-type", None)
    if block_type is None:
        block_type = element.name
    return NODE_TYPE_MAP.get(block_type, "skip")


def get_node_marks(element: Tag) -> list[ProseMirrorMark]:
    marks = []
    if element.name == "b":
        marks.append({"type": "bold"})
    elif element.name == "i":
        marks.append({"type": "italic"})
    elif element.name == "sup":
        marks.append({"type": "superscript"})
    return marks


def convert_element(element: PageElement) -> ProseMirrorNode:
    attrs = {"id": str(uuid4())}
    if isinstance(element, NavigableString):
        return ProseMirrorTextNode(text=element.text, attrs=attrs)
    node_type = get_node_type(element)
    if node_type == "text":
        marks = get_node_marks(element)
        return ProseMirrorTextNode(text=element.text, attrs=attrs, marks=marks)
    child_elements = list(element.children)
    content = [convert_element(child) for child in child_elements]
    if node_type == "heading":
        attrs["level"] = int(element.name[1])
    elif node_type == "math":
        attrs["formula"] = element.find("math").get_text().strip()
    elif node_type == "codeBlock":
        language = element.get("class", [""])[0].replace("language-", "")
        attrs["language"] = language
    elif node_type == "link":
        attrs["href"] = element.get("href", "")
    return ProseMirrorContainerNode(type=node_type, attrs=attrs, content=content)


_converter = None


def __create_html():

    def _get_converter() -> PdfConverter:
        global _converter
        if _converter is None:
            _converter = PdfConverter(
                artifact_dict=create_model_dict(),
                renderer="marker.renderers.json.JSONRenderer",
            )
        return _converter

    def pdf_to_html(pdf: bytes) -> BeautifulSoup:
        converter = _get_converter()
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
            temp_file.write(pdf)
            temp_file.flush()
            rendered = converter(temp_file.name)
        html = ""
        for block in rendered.children:
            html += (
                json_to_html(block) + f'<div block_type="{PAGE_BREAK_SENTINEL}"></div>'
            )

        return BeautifulSoup(html, "html.parser")

    with open("cleanup.pdf", "rb") as f:
        html = pdf_to_html(f.read())

    with open("converted.html", "w+") as f:
        f.write(str(html))


if __name__ == "__main__":
    # __create_html()

    with open("converted.html", "r") as f:
        html = BeautifulSoup(f.read(), "html.parser")

    elements = list(html.children)
    nodes = [html_to_prosemirror(e) for e in elements]
    x = 0
