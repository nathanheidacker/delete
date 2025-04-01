import asyncio
from io import BytesIO

import fitz
from .base import Agent, make_config
from .basev2 import AgentV2, make_config_v2
from .convert import convert
from langchain_openai import ChatOpenAI
from . import prompts
from typing import Literal


class SuggestionAgent:
    llm: ChatOpenAI
    annot_color = (0.8588235294117647, 0.7901960784313725, 0.9784313725490196)

    def get_llm(self) -> ChatOpenAI:
        if self.llm is None:
            self.llm = ChatOpenAI(
                base_url="https://gateway.ai.cloudflare.com/v1/f0d60d63e373ab194adfb2a3ab113aad/genesis/openai",
                temperature=0,
                model_name="gpt-4o-mini",
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

    async def __call__(self, pdf: bytes) -> tuple[str, dict]:
        markdown = convert(pdf)
        results = await self.process(markdown)
        return markdown, results

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


if __name__ == "__main__":
    agent = SuggestionAgent(version=2)
    with open("cleanup.pdf", "rb") as f:
        data = f.read()
        markdown, suggestions = agent(data)
        x = 0
