import asyncio
from io import BytesIO

import fitz
from base import Agent, Suggestion, make_config
from basev2 import AgentV2, make_config_v2
from convert import convert
from langchain_community.chat_models import ChatOpenAI
from tqdm import tqdm
import prompts
from typing import Literal


class SuggestionAgent:
    llm: ChatOpenAI
    annot_color = (0.8588235294117647, 0.7901960784313725, 0.9784313725490196)

    def get_llm(self) -> ChatOpenAI:
        if self.llm is None:
            self.llm = ChatOpenAI(
                base_url="https://gateway.ai.cloudflare.com/v1/f0d60d63e373ab194adfb2a3ab113aad/genesis/openai",
                temperature=0,
                model_name="gpt-4-turbo",
            )
        return self.llm

    def __init__(self, version: Literal[1, 2] = 2):
        self.llm = None
        self.version = version
        self.clarity = self.make_agent(prompts.clarity_prompt)
        self.completeness = self.make_agent(prompts.completeness_prompt)
        self.parsability = self.make_agent(prompts.parsability_prompt)
        self.consistency = self.make_agent(prompts.consistency_prompt)

    def make_agent(self, identifier_prompt: str) -> Agent | AgentV2:
        if self.version == 1:
            config_factory = make_config
            agent_factory = Agent
        if self.version == 2:
            config_factory = make_config_v2
            agent_factory = AgentV2
        else:
            raise ValueError("Invalid version. Please select 1 or 2")

        return agent_factory(self.get_llm(), config_factory(identifier_prompt))

    async def __call__(self, pdf: bytes) -> tuple[bytes, dict]:
        markdown = convert(pdf)
        results = await self.process(markdown)
        doc = fitz.open("pdf", pdf)
        self.annotate_document(doc, results)
        return self.get_arraybuffer(doc), results

    async def process(self, markdown: str) -> dict:
        if self.version == 1:
            results = await asyncio.gather(
                asyncio.to_thread(self.clarity, markdown),
                asyncio.to_thread(self.completeness, markdown),
                asyncio.to_thread(self.parsability, markdown),
                asyncio.to_thread(self.consistency, markdown),
            )
        else:
            results = await asyncio.gather(
                self.clarity(markdown),
                self.completeness(markdown),
                self.parsability(markdown),
                self.consistency(markdown),
            )
        return {
            "clarity": results[0],
            "completeness": results[1],
            "parsability": results[2],
            "consistency": results[3],
        }

    @staticmethod
    def get_arraybuffer(doc: fitz.Document) -> bytes:
        buffer = BytesIO()
        doc.save(buffer)
        return buffer.getvalue()

    def annotate_document(self, doc: fitz.Document, results):
        suggestions = self.gather_suggestions(results)
        with tqdm(
            total=len(suggestions) * doc.page_count, desc="Writing Annotations to PDF"
        ) as pbar:
            for page_id in range(doc.page_count):
                page = doc.load_page(page_id)
                for suggestion in suggestions:
                    pbar.update(1)
                    action_type = suggestion["action_type"]
                    original = suggestion.get("original_text", None)
                    suggested = suggestion.get("suggested_text", None)
                    if original:
                        for search_result in page.search_for(original):
                            if suggested:
                                self.add_annotation(page, search_result, suggested)
                            elif action_type == "remove":
                                self.add_annotation(page, search_result, "DELETE")
                            break

    def add_annotation(
        self, page: fitz.Page, bbox: fitz.Quad | fitz.Rect, content: str
    ):
        annot = page.add_highlight_annot(
            bbox,
        )
        annot.set_colors(stroke=self.annot_color)
        annot.set_info(content=content)
        annot.update()

    def gather_suggestions(self, results) -> list[Suggestion]:
        return [
            suggestion for val in results.values() for suggestion in val["suggestions"]
        ]


async def test_v1_fast():
    agent = SuggestionAgent(version=1)
    with open("test.txt", "r") as f:
        markdown = f.read()
    results = await agent.process(markdown)
    doc = fitz.open("test.pdf")
    agent.annotate_document(doc, results)
    doc.save("annotated.pdf")
    x = 0


async def test_v1_e2e():
    agent = SuggestionAgent(version=1)
    with open("test.bin", "rb") as f:
        data = f.read()
    annotated, suggestions = await agent(data)
    print("document successfully annotated")
    print(len(annotated))
    doc = fitz.open(stream=annotated, filetype="pdf")
    doc.save("annotated.pdf")
    print("document successfully saved!")
    x = 0


async def test_v2_fast():
    agent = SuggestionAgent(version=2)
    with open("test.txt", "r") as f:
        markdown = f.read()
    results = await agent.process(markdown)
    doc = fitz.open("test.pdf")
    agent.annotate_document(doc, results)
    doc.save("annotated.pdf")
    x = 0


async def test_v2_e2e(): ...


def main():
    test_func = test_v2_fast
    asyncio.run(test_func())


if __name__ == "__main__":
    main()
