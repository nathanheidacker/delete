from pydantic import BaseModel, create_model, RootModel
from langchain_core.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain_core.runnables import RunnableSerializable
from langchain.output_parsers import PydanticOutputParser
from typing import List, Type, Literal, Optional
import asyncio


class Problem(BaseModel):
    description: str
    locations: Optional[list[str]] = None


class ActionResponse(BaseModel):
    id: int
    resolution: str


class Issue(Problem):
    id: int
    resolution: str


class Suggestion(BaseModel):
    id: int
    action_type: Literal["add", "replace", "remove"]
    location: str
    original_text: Optional[str] = None
    suggested_text: Optional[str] = None
    explanation: str


class ChainConfig(BaseModel):
    template_text: str
    schema: Type[BaseModel]


default_resolver_template = """
You will be provided with a PRD and a set of issues that have been identified with it.
Based on the identified issues, suggest the best way to resolve each.
For each issue, provide a solution in this format:
- "id": The id of the issue being addressed
- "resolution": The recommended fix

Return the result as a JSON array.

PRD Document:
{prd}

Issues:
{problems}
""".strip()

default_suggester_template = """
You will be provided a product requirement document and an issue that has been identified with it.
You may also be provided with one or more examples of where the issue occurs.
Your goal is to identify all areas in the document where the issue occurs and provide a set of "suggestions" about how each may be improved.
Each suggestion must follow the following structure:
- "id": id of the issue you were provided
- "action_type": "add", "replace", or "remove"
- "location": Line number or text snippet
- "original_text": (if applicable) Current text in the PRD
- "suggested_text": (if applicable) Proposed new text
- "explanation": Why this change is necessary

Return the result as a JSON array.

PRD Document:
{prd}

Identified Issue:
{issue}
""".strip()


class AgentConfig(BaseModel):
    identifier: ChainConfig
    resolver: ChainConfig
    suggester: ChainConfig


def make_config_v2(
    identifier_prompt: str,
    identifier_type: Type[BaseModel] = Problem,
    resolver_prompt: str = default_resolver_template,
    resolver_type: Type[BaseModel] = ActionResponse,
    suggester_prompt: str = default_suggester_template,
    suggester_type: Type[BaseModel] = Suggestion,
) -> AgentConfig:
    return AgentConfig(
        **dict(
            identifier=dict(template_text=identifier_prompt, schema=identifier_type),
            resolver=dict(template_text=resolver_prompt, schema=resolver_type),
            suggester=dict(template_text=suggester_prompt, schema=suggester_type),
        )
    )


def make_chain(
    llm: ChatOpenAI, inputs: list[str], options: ChainConfig
) -> RunnableSerializable:
    for input_label in inputs:
        assert f"{{{input_label}}}" in options.template_text

    template = PromptTemplate(
        input_variables=inputs,
        template=options.template_text,
    )

    ListSchema = create_model(
        f"{options.schema.__name__}Array", __base__=RootModel[List[options.schema]]
    )
    parser = PydanticOutputParser(pydantic_object=ListSchema)
    return template | llm | parser


class AgentV2:
    def __init__(self, llm: ChatOpenAI, config: AgentConfig):
        self.identifier = make_chain(llm, ["prd"], config.identifier)
        self.resolver = make_chain(llm, ["problems"], config.resolver)
        self.suggester = make_chain(llm, ["prd", "issue"], config.suggester)

    async def __call__(self, prd: str):
        problems = self.identifier.invoke({"prd": prd})
        problems = [
            dict(id=i, **problem) for i, problem in enumerate(problems.model_dump())
        ]
        actions = self.resolver.invoke({"prd": prd, "problems": problems})

        issues = {problem["id"]: problem for problem in problems}
        for action in actions.model_dump():
            issues[action["id"]] = issues[action["id"]] | action

        suggestions = await asyncio.gather(
            *[
                asyncio.to_thread(self.suggester.invoke, {"prd": prd, "issue": issue})
                for issue in issues.values()
            ]
        )
        suggestions = [
            suggestion for group in suggestions for suggestion in group.model_dump()
        ]
        return dict(
            issues=list(issues.values()),
            suggestions=suggestions,
        )


async def main():
    llm = ChatOpenAI(
        base_url="https://gateway.ai.cloudflare.com/v1/f0d60d63e373ab194adfb2a3ab113aad/genesis/openai",
        temperature=0,
        model_name="gpt-4-turbo",
    )
    with open("test.txt", "r") as f:
        markdown = f.read()
    from prompts import clarity_prompt

    clarity_config = make_config_v2(clarity_prompt)
    agent = AgentV2(llm, clarity_config)
    results = await agent(markdown)
    x = 0


if __name__ == "__main__":
    asyncio.run(main())
