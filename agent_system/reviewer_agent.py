"""Reviewer agent — quality gate with 3 severity verdicts: missing, tangent, or fake data."""
import os
import sys

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_key
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from .opnbrain import save_conversation, publish_concept, publish_summary, search_brain
from .registry import create_agent, get_agent, list_agents

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    import urllib.request
    import urllib.error

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("REVIEWER_MODEL", os.environ.get("OLLAMA_MODEL", "reviewer-model"))


@function_tool
async def brain_save_note(title: str, content: str, tags: list[str] | str | None = None) -> str:
    """Save a note to brain memory."""
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    path = save_conversation(title=title, model=OLLAMA_MODEL, tags=tags or [],
                             is_chat=False, prompt="", response=content)
    return f"Saved to brain: {path}"


@function_tool
async def brain_track_concept(name: str) -> str:
    """Register a concept in the brain."""
    path = publish_concept(name)
    return f"Concept tracked: {path}" if path else f"Skipped (bad name: {name!r})"


@function_tool
async def brain_search(query: str) -> str:
    """Search the brain's memory."""
    return search_brain(query)


@function_tool
async def brain_publish_summary(name: str, content: str, tags: list[str] | str | None = None) -> str:
    """Publish a structured summary to the brain."""
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    path = publish_summary(name=name, content=content, tags=tags)
    return f"Summary published: {path}" if path else f"Skipped (bad name: {name!r})"


@function_tool
async def list_agent_types() -> str:
    """List all registered agent types."""
    agents = list_agents()
    if not agents:
        return "No agent types registered."
    lines = ["Registered Agent Types:"]
    for a in agents:
        premade = "(premade)" if a.get("is_premade") else ""
        lines.append(f"- {a['name']} {premade}: {a.get('description', '')}")
    return "\n".join(lines)


@function_tool
async def create_agent_type(name: str, instructions: str, description: str = "") -> str:
    """Create a new agent type in the registry.
    
    The new agent will automatically have access to Scrapling web tools,
    Google Trends, and brain memory tools.
    
    Args:
        name: Unique name for the new agent type
        instructions: System instructions defining the agent's behavior and workflow
        description: Brief description of what the agent does
    """
    try:
        agent = create_agent(name=name, instructions=instructions,
                             description=description, is_premade=False)
        return f"Agent type '{agent['name']}' created. Use delegate_to_agent to run it."
    except ValueError as e:
        return str(e)


@function_tool
async def delegate_to_agent(agent_type: str, task: str) -> str:
    """Create and run a specialized agent with a task.
    
    The agent gets Scrapling, Google Trends, and brain tools automatically.
    
    Args:
        agent_type: The type of agent to run (can be pre-made or custom-created)
        task: Clear task description for the agent
    """
    from .base import create_agent_from_definition

    definition = get_agent(agent_type)
    if not definition:
        types = [a["name"] for a in list_agents()]
        return f"Agent type '{agent_type}' not found. Available: {', '.join(types)}"

    async with MCPServerStdio(
        name="Scrapling",
        params={"command": "scrapling", "args": ["mcp"]},
        cache_tools_list=True,
    ) as scrapling:
        agent = await create_agent_from_definition(
            definition=definition,
            extra_mcp_servers=[scrapling],
        )
        result = await Runner.run(agent, task, max_turns=12)
        return result.final_output


@function_tool
async def verify_links(urls: str) -> str:
    """Check whether URLs are real (not hallucinated).
    
    Makes HEAD/GET requests to each URL and reports which resolve.
    
    Args:
        urls: Newline-separated or comma-separated list of URLs to check
    """
    import re
    items = re.split(r"[\n,]+", urls)
    items = [u.strip() for u in items if u.strip()]
    if not items:
        return "No URLs provided."
    results = []
    for url in items:
        try:
            if HAS_HTTPX:
                resp = await httpx.AsyncClient(timeout=10).head(url, follow_redirects=True)
                ok = "✅" if resp.status_code < 400 else "❌"
                size = f" ({len(resp.content)} bytes)" if resp.status_code < 400 else ""
                results.append(f"{ok} {url} → HTTP {resp.status_code}{size}")
            else:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    ok = "✅" if resp.status < 400 else "❌"
                    results.append(f"{ok} {url} → HTTP {resp.status}")
        except Exception as e:
            results.append(f"❌ {url} → ERROR: {e}")
    return "Link Verification:\n" + "\n".join(results)


@function_tool
async def create_review(title: str, subject: str, criteria: list[str]) -> str:
    """Create and save a structured review template to the brain.
    
    Args:
        title: Review title
        subject: What is being reviewed
        criteria: List of review criteria/checklist items
    """
    lines = [f"# Review: {title}", f"**Subject:** {subject}\n"]
    lines.append("## Criteria\n")
    for i, c in enumerate(criteria, 1):
        lines.append(f"{i}. [ ] {c}")
    lines.append("\n## Findings\n\n## Score\n\n## Recommendations\n")
    content = "\n".join(lines)
    path = save_conversation(title=f"Review - {title}", model=OLLAMA_MODEL,
                             tags=["review"], is_chat=False, prompt="", response=content)
    publish_concept(subject)
    return f"Review template saved: {path}\n\n{content}"


def _make_ollama_client():
    return AsyncOpenAI(
        base_url=f"{OLLAMA_URL}/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
    )


async def create_reviewer_agent() -> Agent:
    client = _make_ollama_client()
    model = OpenAIChatCompletionsModel(model=OLLAMA_MODEL, openai_client=client)
    set_default_openai_key("ollama")

    return Agent(
        name="ReviewerAgent",
        instructions=(
            "You are a Reviewer agent — the strict quality gate. You ONLY review results against a goal."
            " You NEVER delegate, create agents, or do research."
            " Your sole job is to compare RESULTS against GOAL and output a VERDICT.\n\n"
            "## VERDICT FORMAT\n"
            "Your final output MUST contain exactly one of these on its own line:\n"
            "    **SEVERITY: ALL MET**\n"
            "    **SEVERITY: MISSING**\n"
            "    **SEVERITY: TANGENT**\n"
            "    **SEVERITY: FAKE DATA**\n\n"
            "### ALL MET (success)\n"
            "Use when: Every requirement is fully satisfied with real, verifiable results.\n"
            "Output: **SEVERITY: ALL MET** and **ALL GOALS MET**\n\n"
            "### MISSING (incomplete)\n"
            "Use when: On-topic but incomplete. Some requirements unmet.\n"
            "Output: **SEVERITY: MISSING** then **REMAINING GAPS:** with numbered list.\n\n"
            "### TANGENT (off-topic)\n"
            "Use when: Output doesn't address the stated goal.\n"
            "Output: **SEVERITY: TANGENT** then **ORIGINAL GOAL:** restated.\n\n"
            "### FAKE DATA (fabricated)\n"
            "Use when: Results are simulated/fabricated instead of real tool execution.\n"
            "Call `verify_links` on any URLs to check if claims are real.\n"
            "Output: **SEVERITY: FAKE DATA** then **EVIDENCE:** describing what was fabricated.\n\n"
            "## RULES\n"
            "- Do NOT call delegate_to_agent — you have no such tool\n"
            "- Do NOT create agents or list agents — you have no such tool\n"
            "- MORE DATA IS BETTER. Extra findings beyond the requested count are fine.\n"
            "- Minor formatting or phrasing differences are NOT gaps.\n"
            "- Only flag a MISSING if the GOAL was substantively unmet (e.g., no real data, wrong topic entirely).\n"
            "- If you suspect fake data, use verify_links to check URLs\n"
            "- Your output MUST contain the **SEVERITY:** line — this is how the orchestrator parses your verdict"
        ),
        model=model,
        tools=[
            verify_links,
            brain_search,
            brain_track_concept,
            brain_save_note,
            brain_publish_summary,
        ],
    )


def _is_function_call(delta: str) -> bool:
    stripped = delta.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return True
    if stripped.startswith('{"') and ('":"' in stripped or '":' in stripped):
        return True
    return False


async def run_reviewer(task: str, max_turns: int = 20) -> str:
    agent = await create_reviewer_agent()
    print(f"  ⚙ Reviewer thinking...")
    result = Runner.run_streamed(agent, task, max_turns=max_turns)
    chunks = []
    async for event in result.stream_events():
        if event.type == "raw_response_event" and hasattr(event.data, "delta"):
            delta = event.data.delta
            if delta and not _is_function_call(delta):
                print(delta, end="", flush=True)
                chunks.append(delta)
        elif event.type == "agent_updated_stream_event":
            print(f"\n  ⚙ → {event.new_agent.name} speaking...\n", flush=True)
    print(f"\n  ⚙ Reviewer finished")
    return "".join(chunks)
