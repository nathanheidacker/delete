from __future__ import annotations
from pydantic import BaseModel
from typing import Literal, Any, Union, Optional
from bs4.element import PageElement, NavigableString, Tag
from bs4 import BeautifulSoup
from uuid import uuid4
import json
import openai

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


llm = openai.OpenAI(
    base_url="https://gateway.ai.cloudflare.com/v1/f0d60d63e373ab194adfb2a3ab113aad/genesis/openai"
)

system_prompt_old = """
You will be provided with the following:
- A Product Requirements Document (PRD) in markdown
- A list of issues identified with the document
- A list of suggestions to improve the document
- A ProseMirror representation of the PRD

Your task is to implement the suggested change by editing the given ProseMirror node.
ProseMirror nodes have the following schema:

type ProseMirrorNodeTypeString =
  | "math"
  | "paragraph"
  | "heading"
  | "listItem"
  | "bulletList"
  | "doc"
  | "codeBlock"
  | "blockQuote"
  | "tableRow"
  | "tableHeader"
  | "tableCell"
  | "table"
  | "image"
  | "text"
  | "link"
  | "skip";

type ProseMirrorMarkTypeString =
  | "bold"
  | "italic"
  | "superscript"
  | "color"
  | "strikethrough"
  | "link";

interface ProseMirrorMark {
  type: ProseMirrorMarkTypeString;
  attrs?: Record<string, any>;
}

interface ProseMirrorTextNode {
  type: "text";
  attrs?: Record<string, any>;
  text: string;
  marks?: ProseMirrorMark[];
}

interface ProseMirrorContainerNode {
  type: ProseMirrorNodeTypeString;
  attrs?: Record<string, any>;
  content: ProseMirrorNode[];
  marks?: ProseMirrorMark[];
}

type ProseMirrorNode = ProseMirrorTextNode | ProseMirrorContainerNode;

For the attrs, all nodes will contain an id with a uuid. 
headings will contain an integer value 'level' attr corresponding to their heading level.
math nodes will contain a 'formula' attr corresponding to the latex formula to be displayed
codeBlock nodes will contain a 'language' attr corresponding to the language used to write the code

You may add marks wherever you deem necessary to draw attention, provide emphasis, etc.

Your response MUST contain only a single valid JSON block which adheres to the above schema, providing a single node.
Your returned node must contain the same id as the one provided to you originally.
"""

system_prompt = """
You will be provided with the following:
- A Product Requirements Document (PRD) in markdown
- A list of issues identified with the document
- A list of suggestions to improve the document
- A ProseMirror representation of the PRD

Your task is to create a mapping from suggestions to ProseMirror nodes, by identifying which node each suggestion is referring to.
All suggestions will have an integer id, and all nodes will have a UUID under key 'id' inside of the 'attrs' field.
Your response must be a single JSON object mapping each suggestion id to a UUID (corresponding to the correct ProseMirror node)

Example:
```json
{
    "0": "d54deec3-e0b0-4e40-a07f-762d0251e6c2",
    "1": "8ab4519e-0beb-4fad-9bc5-5162d7ef43fb",
    "2": "15b6e620-8bd7-46f0-84bd-38414c1e05fc",
    "3": "69cc68bf-ac9f-441b-b32e-384d067fb0aa",
    "4": "b50c8dc1-54ba-4d9f-a840-987a965f7e6e",
    ...
}
```

If the suggestion action_type is "add" (meaning the node doesn't exist yet), please select the UUID of the node IMMEDIATELY PRECEDING the location of the new content.
"""

user_prompt = """
<prd>{PRD}</prd>

<problems>{PROBLEMS}<problems>

<suggestions>{SUGGESTIONS}</suggestions>

<nodes>{NODES}</nodes>
"""


def create_user_prompt(prd: str, suggestion: dict, node: dict) -> str:
    return user_prompt.format(PRD=prd, SUGGESTION=suggestion, NODE=node)


def update_suggestions(data):
    for category, suggestions in data.items():
        for i, suggestion in enumerate(suggestions["suggestions"]):
            suggestion["category"] = category
            suggestion["problem_id"] = suggestion["id"]
            suggestion["id"] = i


def get_formatted_prompts(data):
    prompts = {}
    for category, category_data in data["suggestions"].items():
        prompts[category] = user_prompt.format(
            PRD=data["markdown"],
            PROBLEMS=category_data["issues"],
            SUGGESTIONS=category_data["suggestions"],
            NODES=data["nodes"],
        )
    return prompts


def extract_codeblocks(markdown: str) -> list[str]:
    codeblocks = []
    current_block = ""
    is_block = False
    for line in markdown.split("\n"):
        if line.startswith("```"):
            if is_block:
                codeblocks.append(current_block)
                current_block = ""
            is_block = not is_block
            continue
        if is_block:
            current_block += line + "\n"
    if current_block:
        codeblocks.append(current_block)
    return codeblocks


def create_mapping(markdown: str, suggestions, nodes):
    update_suggestions(suggestions)
    prompts = get_formatted_prompts(data)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompts["clarity"]},
    ]


if __name__ == "__main__":
    with open("test_result.json", "r") as f:
        data = json.load(f)
    nodes = [ProseMirrorContainerNode(**node) for node in data["nodes"]["content"]]
    update_suggestions(data["suggestions"])
    prompts = get_formatted_prompts(data)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompts["clarity"]},
    ]
    response = llm.chat.completions.create(
        model="gpt-4o-mini", messages=messages, temperature=0.0
    )
    raw_mapping = response.choices[0].message.content
    mapping = json.loads(extract_codeblocks(raw_mapping))
    for issue_id, node_id in mapping:
        ...
    x = 0
