"""Base agent factory — creates OpenAI Agents SDK Agent instances from definitions."""
import os

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

from openai import AsyncOpenAI
from agents import Agent, function_tool, set_default_openai_key
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from .opnbrain import (
    save_conversation,
    publish_concept,
    publish_summary,
    search_brain,
)
from .registry import resolve_instructions
from research_agent.tools.google_trends import google_trends_check, google_trends_compare

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b-128k")

# ── Immutable core function tools ────────────────────────────────────


@function_tool
async def check_trends(keywords: list[str], timeframe: str = "today 12-m", geo: str = "") -> str:
    """Check Google Trends interest for keywords to validate market demand."""
    return await google_trends_check(keywords, timeframe, geo)


@function_tool
async def validate_with_trends(product_idea: str, related_terms: list[str] | None = None) -> str:
    """Compare a product/idea against related terms to see relative demand."""
    return await google_trends_compare(product_idea, related_terms)


@function_tool
async def brain_save_note(
    title: str,
    content: str,
    tags: list[str] | str | None = None,
    model: str = "",
) -> str:
    """Save a note or conversation to the brain for persistent memory.
    
    Args:
        title: Short descriptive title (3-8 words)
        content: The note body in markdown
        tags: Optional category tags (comma-separated string or list)
        model: Model name used (default empty)
    """
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    path = save_conversation(
        title=title,
        model=model or OLLAMA_MODEL,
        tags=tags or [],
        is_chat=False,
        prompt="",
        response=content,
    )
    return f"Saved to brain: {path}"


@function_tool
async def brain_track_concept(name: str) -> str:
    """Register a concept in the brain so it gets a wiki page.
    
    Args:
        name: The concept name
    """
    path = publish_concept(name)
    return f"Concept tracked: {path}" if path else f"Skipped (bad name: {name!r})"


@function_tool
async def brain_search(query: str) -> str:
    """Search the brain's memory for past notes and concepts.
    
    Args:
        query: Search keywords
    """
    return search_brain(query)


@function_tool
async def brain_publish_summary(
    name: str,
    content: str,
    tags: list[str] | str | None = None,
) -> str:
    """Publish a structured summary to the brain.
    
    Args:
        name: Summary topic name
        content: Summary body
        tags: Related concept tags (comma-separated string or list)
    """
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    path = publish_summary(name=name, content=content, tags=tags)
    return f"Summary published: {path}" if path else f"Skipped (bad name: {name!r})"


CORE_FUNCTION_TOOLS = [
    check_trends,
    validate_with_trends,
    brain_save_note,
    brain_track_concept,
    brain_search,
    brain_publish_summary,
]


def _make_ollama_client():
    return AsyncOpenAI(
        base_url=f"{OLLAMA_URL}/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
    )


async def create_agent_from_definition(
    definition: dict,
    extra_mcp_servers: list | None = None,
) -> Agent:
    """Create an Agent instance from a registry definition."""
    client = _make_ollama_client()
    model = OpenAIChatCompletionsModel(model=OLLAMA_MODEL, openai_client=client)
    set_default_openai_key("ollama")

    mcp_servers = list(extra_mcp_servers or [])
    tools = list(CORE_FUNCTION_TOOLS)

    instructions = resolve_instructions(definition)

    return Agent(
        name=f"{definition['name']}Agent",
        instructions=instructions,
        model=model,
        mcp_servers=mcp_servers,
        tools=tools,
    )
