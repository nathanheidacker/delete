from __future__ import annotations
from pydantic import BaseModel
from typing import Literal, Any, Union, Optional
from bs4.element import PageElement, NavigableString, Tag
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import json_to_html
from bs4 import BeautifulSoup
import tempfile
from uuid import uuid4

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
    "bold", "italic", "superscript", "color", "strikethrough", "link"
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

    def get_text(self) -> list[str]:
        return [self.text]


class ProseMirrorContainerNode(BaseModel):
    type: ProseMirrorNodeTypeString
    attrs: dict[str, Any] = {}
    content: list[ProseMirrorNode] = []
    marks: list[ProseMirrorMark] = []

    def get_text(self) -> list[str]:
        result = []
        for child in self.content:
            result.extend(child.get_text())
        return result


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
    "li": "listItem",
    "ListItem": "listItem",
    "blockquote": "blockQuote",
    "Equation": "math",
    "Text": "text",
    "b": "text",
    "i": "text",
    "a": "text",
}


def get_node_type(element: Tag) -> ProseMirrorNodeTypeString:
    block_type = element.get("block-type", None)
    if block_type is None:
        block_type = element.name
    return NODE_TYPE_MAP.get(block_type, "skip")


def get_node_marks(element: Tag) -> list[ProseMirrorMark]:
    marks = []
    if element.name == "b":
        marks.append(ProseMirrorMark(type="bold"))
    elif element.name == "i":
        marks.append(ProseMirrorMark(type="italic"))
    elif element.name == "sup":
        marks.append(ProseMirrorMark(type="superscript"))
    elif element.name == "a":
        marks.append(
            ProseMirrorMark(type="link", attrs={"href": element.get("href", "")})
        )
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
    return ProseMirrorContainerNode(type=node_type, attrs=attrs, content=content)


def flatten_nodes(nodes: list[ProseMirrorNode]) -> list[ProseMirrorNode]:
    flattened = []
    for node in nodes:
        if isinstance(node, ProseMirrorContainerNode):
            node.content = flatten_nodes(node.content)
            if node.type == "skip":
                flattened.extend(node.content)
                continue
        else:
            if not node.text:
                continue
        flattened.append(node)
    return flattened


def create_top_level_paragraphs(nodes: list[ProseMirrorNode]):
    for i, node in enumerate(nodes):
        if isinstance(node, ProseMirrorTextNode):
            nodes[i] = ProseMirrorContainerNode(type="paragraph", content=[node])


def html_to_prosemirror(html: BeautifulSoup) -> list[ProseMirrorNode]:
    nodes = [convert_element(e) for e in html.children]
    nodes = flatten_nodes(nodes)
    create_top_level_paragraphs(nodes)
    return nodes


_converter = None


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
        html += json_to_html(block) + f'<div block_type="{PAGE_BREAK_SENTINEL}"></div>'

    return BeautifulSoup(html, "html.parser")


def convert(pdf: bytes) -> dict[str, Any]:
    html = pdf_to_html(pdf)
    nodes = html_to_prosemirror(html)
    return {"type": "doc", "content": [node.model_dump() for node in nodes]}


def query_node_text(
    text: str, nodes: list[ProseMirrorNode]
) -> Optional[ProseMirrorNode]:
    for node in nodes:
        node_text = node.get_text()
        if text in node_text or text in "".join(node_text):
            if isinstance(node, ProseMirrorContainerNode):
                deeper = query_node_text(text, node.content)
                if deeper is not None:
                    return deeper
                return node
    return None


def get_element_text(element: PageElement) -> list[str]:
    if isinstance(element, NavigableString):
        return [element.text]
    result = []
    for child in element.children:
        result.extend(get_element_text(child))
    return result


def query_element_text(text: str, elements: list[PageElement]) -> Optional[PageElement]:
    for element in elements:
        element_text = get_element_text(element)
        if text in "".join(element_text):
            if text in element_text and isinstance(element, Tag):
                return query_element_text(text, element.contents)
            else:
                return element
    return None


def query_all_node_text(
    text: str, nodes: list[ProseMirrorNode]
) -> list[ProseMirrorNode]:
    found = []
    for node in nodes:
        node_text = node.get_text()
        if text in node_text or text in "".join(node_text):
            if isinstance(node, ProseMirrorContainerNode):
                deeper = query_all_node_text(text, node.content)
                if deeper:
                    found.extend(deeper)
                else:
                    found.append(node)
    return found


if __name__ == "__main__":
    with open("converted.html", "r") as f:
        html = BeautifulSoup(f.read())
        nodes = html_to_prosemirror(html)

        search_text = "As a user, I want to convert the recorded steps into"
        node = query_node_text(search_text, nodes)
        element = query_element_text(search_text, html.contents)

        raw_nodes = [convert_element(e) for e in html.children]
        raw_node = query_node_text(search_text, raw_nodes)
        x = 0
