from pydantic import BaseModel, create_model, RootModel
from langchain_core.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain_core.runnables import RunnableSerializable
from langchain.output_parsers import PydanticOutputParser
from typing import List, Type, Literal, Optional


class Problem(BaseModel):
    description: str
    location: Optional[str] = None


class Action(BaseModel):
    description: str
    resolution: str


class Suggestion(BaseModel):
    action_type: Literal["add", "replace", "remove"]
    location: str
    original_text: Optional[str] = None
    suggested_text: Optional[str] = None
    explanation: str


class ChainConfig(BaseModel):
    template_text: str
    schema: Type[BaseModel]


default_resolver_template = """
Based on the identified issues, suggest the best way to resolve each.
For each issue, provide a solution in this format:
- "description": The identified issue
- "resolution": The recommended fix

Return the result as a JSON array.

Inconsistencies:
{problems}
""".strip()

default_suggester_template = """
Based on these resolutions, generate precise change suggestions.
Each suggestion must include:
- "action_type": "add", "replace", or "remove"
- "location": Line number or text snippet
- "original_text": (if applicable) Current text in the PRD
- "suggested_text": (if applicable) Proposed new text
- "explanation": Why this change is necessary

Return the result as a JSON array.

PRD Document:
{prd}
Suggested Actions:
{actions}
""".strip()


class AgentConfig(BaseModel):
    identifier: ChainConfig
    resolver: ChainConfig
    suggester: ChainConfig


def make_config(
    identifier_prompt: str,
    identifier_type: Type[BaseModel] = Problem,
    resolver_prompt: str = default_resolver_template,
    resolver_type: Type[BaseModel] = Action,
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


class Agent:
    def __init__(self, llm: ChatOpenAI, config: AgentConfig):
        self.identifier = make_chain(llm, ["prd"], config.identifier)
        self.resolver = make_chain(llm, ["problems"], config.resolver)
        self.suggester = make_chain(llm, ["prd", "actions"], config.suggester)

    def __call__(self, prd: str):
        problems = self.identifier.invoke({"prd": prd})
        actions = self.resolver.invoke({"problems": problems})
        suggestions = self.suggester.invoke({"prd": prd, "actions": actions})
        return dict(
            problems=problems.model_dump(),
            actions=actions.model_dump(),
            suggestions=suggestions.model_dump(),
        )
