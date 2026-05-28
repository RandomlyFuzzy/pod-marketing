"""General-purpose agent with Scrapling (web), Google Trends, and opnbrain (memory)."""
import os

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_key
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from agent_system.opnbrain import (
    save_conversation,
    publish_concept,
    publish_summary,
    search_brain,
)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b-128k")

_GLOBAL_SERVER_REF = None


# ── opnbrain function tools ──────────────────────────────────────────

@function_tool
async def brain_save_note(
    title: str,
    content: str,
    tags: list[str] | str | None = None,
    model: str = "",
) -> str:
    """Save a note or conversation to the brain for persistent memory.
    
    Use this to log research findings, ideas, decisions, or any output you produce.
    The brain will automatically extract concepts and build wiki-links.
    
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
    
    Use this for important ideas, products, people, or terms you encounter.
    
    Args:
        name: The concept name
    """
    path = publish_concept(name)
    return f"Concept tracked: {path}" if path else f"Skipped (bad name: {name!r})"


@function_tool
async def brain_search(query: str) -> str:
    """Search the brain's memory for past notes and concepts.
    
    Use this before starting new work to recall what was already done.
    
    Args:
        query: Search keywords
    """
    return search_brain(query)


@function_tool
async def brain_publish_summary(
    name: str,
    content: str,
    tags: list[str] | None = None,
) -> str:
    """Publish a structured summary to the brain.
    
    Use this to create reference cards for topics you've researched deeply.
    
    Args:
        name: Summary topic name
        content: Summary body
        tags: Related concept tags
    """
    path = publish_summary(name=name, content=content, tags=tags)
    return f"Summary published: {path}" if path else f"Skipped (bad name: {name!r})"


# ── Google Trends function tools ─────────────────────────────────────

from research_agent.tools.google_trends import google_trends_check, google_trends_compare


@function_tool
async def check_trends(keywords: list[str], timeframe: str = "today 12-m", geo: str = "") -> str:
    """Check Google Trends interest for keywords to validate market demand.
    
    Args:
        keywords: List of search terms to check (max 5)
        timeframe: Time range ('today 3-m', 'today 12-m', 'today 5-y', 'all')
        geo: Region ('US', 'GB', etc, or '' for worldwide)
    """
    return await google_trends_check(keywords, timeframe, geo)


@function_tool
async def validate_with_trends(product_idea: str, related_terms: list[str] | None = None) -> str:
    """Compare a product/idea against related terms to see relative demand.
    
    Args:
        product_idea: The main topic to check
        related_terms: Optional related terms to compare against
    """
    return await google_trends_compare(product_idea, related_terms)


# ── Agent factory ────────────────────────────────────────────────────

def _make_ollama_client():
    return AsyncOpenAI(
        base_url=f"{OLLAMA_URL}/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
    )


async def create_general_agent(scrapling_server=None) -> Agent:
    client = _make_ollama_client()
    model = OpenAIChatCompletionsModel(model=OLLAMA_MODEL, openai_client=client)
    set_default_openai_key("ollama")

    mcp_servers = []
    if scrapling_server:
        mcp_servers = [scrapling_server]

    return Agent(
        name="GeneralAgent",
        instructions=(
            "You are a versatile general-purpose agent. You can research, analyze, "
            "write, plan, and create content on any topic.\n\n"
            "YOUR AVAILABLE TOOLS (use these exact names):\n"
            "1. **`get`** — Make HTTP GET request to fetch a web page (use for Google searches, "
            "e.g. `get(url='https://www.google.com/search?q=YOUR_QUERY')`)\n"
            "2. **`fetch`** — Use Playwright browser to fetch a JavaScript-heavy page\n"
            "3. **`stealthy_fetch`** — Fetch pages with anti-bot protection\n"
            "4. **`bulk_get`** / **`bulk_fetch`** — Fetch multiple URLs at once\n"
            "5. **`check_trends`** — Google Trends: check search interest for keywords\n"
            "6. **`validate_with_trends`** — Compare a product/idea against related terms\n"
            "7. **`brain_save_note`** — Save notes to persistent brain memory\n"
            "8. **`brain_track_concept`** — Register important concepts\n"
            "9. **`brain_search`** — Search previous work in the brain\n"
            "10. **`brain_publish_summary`** — Create reference summaries\n\n"
            "WORKFLOW:\n"
            "- For web searches, call `get(url='https://www.google.com/search?q=YOUR_QUERY')`\n"
            "- Validate demand with `check_trends(keywords=['term1', 'term2'])`\n"
            "- Save important findings with `brain_save_note(title=..., content=...)`\n"
            "- Track key concepts with `brain_track_concept(name=...)`\n"
            "- Check memory first with `brain_search(query=...)` before repeating work\n"
            "- Produce thorough, well-structured output with data and sources\n\n"
            "CRITICAL RULES:\n"
            "- Do NOT make up tool names. Only use the tools listed above.\n"
            "- Do NOT call `google_search`, `search`, or `Scrapling` — those don't exist.\n"
            "- For web searches, always use `get()`.\n"
            "- Call tools with named parameters (e.g. `get(url='...')`)."
        ),
        model=model,
        mcp_servers=mcp_servers,
        tools=[
            check_trends,
            validate_with_trends,
            brain_save_note,
            brain_track_concept,
            brain_search,
            brain_publish_summary,
        ],
    )
