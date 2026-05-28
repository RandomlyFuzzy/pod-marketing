"""General research agent using OpenAI Agents SDK with MCP tools (Scrapling + Google Trends)."""
import os

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_key
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from .tools.google_trends import google_trends_check, google_trends_compare

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b-128k")


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


def _make_ollama_client():
    return AsyncOpenAI(
        base_url=f"{OLLAMA_URL}/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
    )


async def create_scrapling_server():
    server = MCPServerStdio(
        name="Scrapling",
        params={
            "command": "scrapling",
            "args": ["mcp"],
        },
        cache_tools_list=True,
    )
    await server.connect()
    return server


async def create_agent(mcp_enabled: bool = True, instructions: str = "",
                       scrapling_server=None) -> Agent:
    client = _make_ollama_client()
    model = OpenAIChatCompletionsModel(model=OLLAMA_MODEL, openai_client=client)
    set_default_openai_key("ollama")

    mcp_servers = []
    if mcp_enabled and scrapling_server:
        mcp_servers = [scrapling_server]

    return Agent(
        name="ResearchAgent",
        instructions=(
            instructions
            or """You are a general research agent. Your job is to research any topic thoroughly.

YOUR AVAILABLE TOOLS — Use ONLY these:
1. **Scrapling tools** (`get`, `bulk_get`, `fetch`, `bulk_fetch`, `stealthy_fetch`, `open_session`, `screenshot`) — for fetching web pages and searching the web
2. **`check_trends`** — Google Trends: check search interest for keywords
3. **`validate_with_trends`** — compare a product/idea against related terms

Research workflow:
1. Start by using Scrapling's `get` tool to search for information. For Google searches, fetch URLs like `https://www.google.com/search?q=YOUR_SEARCH`
2. Use `check_trends` to validate demand and interest
3. Synthesize findings into a clear, structured report

CRITICAL: Do NOT use any tools other than the ones listed above. Do NOT call `google_search` or any search tool that isn't listed. Use Scrapling's `get` or `fetch` tools for all web searches.

Always provide:
- Specific data and sources where possible
- Trend direction (growing, stable, declining)
- Key players, products, or offerings
- Target audience insights
- Actionable recommendations

If the topic is about products or markets, include pricing and competitive analysis.
If the topic is about a trend or concept, focus on trajectory and implications.
"""
        ),
        model=model,
        mcp_servers=mcp_servers,
        tools=[check_trends, validate_with_trends],
    )


async def research_topic(topic: str, instructions: str = "", max_turns: int = 15) -> str:
    """Run research on a topic using the agent with Scrapling + Google Trends."""
    async with MCPServerStdio(
        name="Scrapling",
        params={"command": "scrapling", "args": ["mcp"]},
        cache_tools_list=True,
    ) as scrapling:
        agent = await create_agent(
            instructions=instructions or f"Research this topic thoroughly: {topic}",
            scrapling_server=scrapling,
        )
        result = await Runner.run(
            agent,
            f"Research this topic: {topic}\n\n"
            f"1. Use Scrapling's `get` tool to search the web for current info\n"
            f"2. Use `check_trends` to validate demand via Google Trends\n"
            f"3. Produce a comprehensive research report",
            max_turns=max_turns,
        )
        return result.final_output
