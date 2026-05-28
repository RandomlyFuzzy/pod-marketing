"""Planner agent — mini-orchestrator that decomposes goals and executes sub-tasks via delegation."""
import os
import json
from datetime import datetime

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_key
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from .opnbrain import save_conversation, publish_concept, search_brain
from .registry import create_agent, get_agent, list_agents, team_manifest

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    import urllib.request
    import urllib.error

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("PLANNER_MODEL", os.environ.get("OLLAMA_MODEL", "planner-model"))
PLANNER_STORE = os.environ.get("PLANNER_STORE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "planner_store"))
SCRAPLING_MCP_TIMEOUT = float(os.environ.get("SCRAPLING_MCP_TIMEOUT", "30"))
os.makedirs(PLANNER_STORE, exist_ok=True)


# ── Persistent result storage between delegation steps ──

@function_tool
async def store_result(key: str, content: str) -> str:
    """Save a step result for use by later steps.
    
    After calling delegate_to_agent, call this to persist the result
    so the next step can retrieve it.
    
    Args:
        key: Unique identifier like "step_1", "step_2"
        content: The raw output from delegate_to_agent
    """
    path = os.path.join(PLANNER_STORE, f"{key}.json")
    with open(path, "w") as f:
        json.dump({"key": key, "content": content, "timestamp": datetime.now().isoformat()}, f)
    return f"Stored: {key} ({len(content)} chars)"


@function_tool
async def load_result(key: str) -> str:
    """Load a previously stored step result.
    
    Call this when building the task for the next step to include
    prior results as context.
    
    Args:
        key: The key used in store_result
    """
    path = os.path.join(PLANNER_STORE, f"{key}.json")
    if not os.path.exists(path):
        return f"No stored result for: {key}"
    with open(path) as f:
        return json.load(f)["content"]


@function_tool
async def list_results() -> str:
    """List all available stored results."""
    files = [f.replace(".json", "") for f in os.listdir(PLANNER_STORE) if f.endswith(".json")]
    return "\n".join(sorted(files)) if files else "No stored results."


@function_tool
async def store_context(key: str, summary: str) -> str:
    """Save a context summary for the next orchestrator iteration.
    
    Args:
        key: Identifier like "iteration_1_summary"
        summary: What was learned, what's still needed
    """
    path = os.path.join(PLANNER_STORE, f"ctx_{key}.json")
    with open(path, "w") as f:
        json.dump({"key": key, "summary": summary, "timestamp": datetime.now().isoformat()}, f)
    return f"Context saved: {key}"


@function_tool
async def load_context(key: str) -> str:
    """Load a context summary from a previous iteration.
    
    Args:
        key: Identifier like "iteration_1_summary"
    """
    path = os.path.join(PLANNER_STORE, f"ctx_{key}.json")
    if not os.path.exists(path):
        return f"No context for: {key}"
    with open(path) as f:
        return json.load(f)["summary"]


# ── Other tools ──

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
async def list_agent_types() -> str:
    """List all registered agent types, models, and effective tools."""
    return team_manifest()


@function_tool
async def get_team_manifest() -> str:
    """Return every registered agent with its model, function tools, and MCP tools."""
    return team_manifest()


@function_tool
async def create_agent_type(name: str, instructions: str, description: str = "") -> str:
    """Create a new agent type in the registry."""
    try:
        agent = create_agent(name=name, instructions=instructions,
                             description=description, is_premade=False)
        return f"Agent type '{agent['name']}' created. Use delegate_to_agent to run it."
    except ValueError as e:
        return str(e)


@function_tool
async def verify_links(urls: str) -> str:
    """Check whether URLs are real (not hallucinated)."""
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
async def delegate_to_agent(agent_type: str, task: str) -> str:
    """RUN a specialized agent with a task.
    
    The agent gets Scrapling, Google Trends, and brain tools automatically.
    After calling this, use store_result(key, result) to persist the output.
    
    Args:
        agent_type: The type of agent to run (pre-made or custom)
        task: Clear task description. Include prior results by calling load_result(key) first.
    """
    from .base import create_agent_from_definition

    # Always use 'researcher' agent for research/web data tasks if the requested agent is not found or is not suitable
    definition = get_agent(agent_type)
    fallback_to_researcher = False
    if not definition:
        # If the requested agent is not found and the task is research-like, fallback to 'researcher'
        if any(kw in task.lower() for kw in ["search", "find", "current", "web", "temperature", "ip address", "weather", "news", "lookup", "data", "information"]):
            definition = get_agent("researcher")
            fallback_to_researcher = True
    # If still not found, error out
    if not definition:
        types = [a["name"] for a in list_agents()]
        return f"Agent type '{agent_type}' not found. Available: {', '.join(types)}"

    async with MCPServerStdio(
        name="Scrapling",
        params={"command": "scrapling", "args": ["mcp"]},
        cache_tools_list=True,
        client_session_timeout_seconds=SCRAPLING_MCP_TIMEOUT,
    ) as scrapling:
        agent = await create_agent_from_definition(
            definition=definition,
            extra_mcp_servers=[scrapling],
        )
        # If we fell back to researcher, clarify in the task
        if fallback_to_researcher:
            task = f"[FALLBACK: researcher agent used for web data access] {task}"
        result = await Runner.run(agent, task, max_turns=12)
        return result.final_output


@function_tool
async def create_plan(title: str, phases: str) -> str:
    """Create and save a multi-phase plan to the brain."""
    lines = [f"# Plan: {title}\n"]
    for i, line in enumerate(phases.strip().split("\n"), 1):
        parts = [p.strip() for p in line.split("|")]
        name = parts[0] if parts else f"Phase {i}"
        agent_type = parts[1] if len(parts) > 1 else ""
        goal = parts[2] if len(parts) > 2 else ""
        lines.append(f"## Phase {i}: {name}")
        lines.append(f"**Agent:** {agent_type}")
        lines.append(f"**Goal:** {goal}\n")
    content = "\n".join(lines)
    path = save_conversation(title=f"Plan - {title}", model=OLLAMA_MODEL,
                             tags=["plan"], is_chat=False, prompt="", response=content)
    for line in phases.strip().split("\n"):
        name = line.split("|")[0].strip() if "|" in line else line.strip()
        if name:
            publish_concept(name)
    return f"Plan saved: {path}\n\n{content}"


def _make_ollama_client():
    return AsyncOpenAI(
        base_url=f"{OLLAMA_URL}/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
    )


async def create_planner_agent() -> Agent:
    client = _make_ollama_client()
    model = OpenAIChatCompletionsModel(model=OLLAMA_MODEL, openai_client=client)
    set_default_openai_key("ollama")

    manifest = team_manifest()

    return Agent(
        name="PlannerAgent",
        instructions=(
            "You are a Planner agent — a mini-orchestrator. "
            "Your job: decompose goals into sequential steps, execute each step, "
            "persist results, and output ACTUAL RAW DATA.\n\n"
            "## TEAM MANIFEST\n"
            f"{manifest}\n\n"
            "## EXECUTION RULES\n"
            "1. Before delegating, choose an agent from the TEAM MANIFEST by name.\n"
            "2. For simple memory lookups: call brain_search() directly.\n"
            "3. For current web data: delegate to researcher, scourer, competitive_analyst, or market_validator.\n"
            "4. For platform/POD work: delegate to listing_optimizer, margin_analyst, production_advisor, or product_strategist.\n"
            "5. For code work: delegate to architect, code_writer, debugger, tester, or code_reviewer.\n"
            "6. After each result: call store_result(key, <raw returned data>).\n"
            "7. Before next step: call load_result(key) to get prior data.\n"
            "8. INCLUDE prior data verbatim in the next step's task.\n"
            "9. At end: call store_context(\"iteration_N\", summary).\n\n"
            "Do not invent agent names. If no listed agent fits, call create_agent_type first.\n\n"
            "## TOOL USE REQUIREMENT\n"
            "If the goal asks you to execute work, you must call at least one relevant tool before final output. "
            "A written plan without tool results is a failed response.\n\n"
            "## DIRECT TOOL RULES\n"
            "1. For simple lookups: call brain_search() directly (it's a function tool)\n"
            "2. For complex sub-tasks: call delegate_to_agent(agent_type, task)\n"
            "3. After each result: call store_result(key, <raw returned data>)\n"
            "4. Before next step: call load_result(key) to get prior data\n"
            "5. INCLUDE prior data verbatim in the next step's task\n"
            "6. At end: call store_context(\"iteration_N\", summary)\n\n"
            "## FALLBACK CHAIN\n"
            "If a step returns error/empty:\n"
            "  Try: different agent type → create_agent_type → brain_search\n"
            "  3 attempts max, then report specific failure.\n\n"
            "## OUTPUT FORMAT — RAW DATA ONLY\n"
            "  === DATA FROM STEP 1 ===\n"
            "  [RAW tool output — verbatim, not summarized]\n"
            "  === DATA FROM STEP 2 ===\n"
            "  [RAW tool output]\n"
            "  === SYNTHESIS ===\n"
            "  [your analysis]\n\n"
            "NO process descriptions. NO plans. NO intentions. OUTPUT RAW DATA.\n"
            "NO markdown code fences around DATA sections.\n\n"
            "## TOOLS\n"
            "Direct call tools (call directly):\n"
            "- brain_search(query) — search memory\n"
            "- verify_links(urls) — check if URLs are real\n"
            "- store_result(key, content) / load_result(key) / list_results()\n"
            "- store_context(key) / load_context(key)\n"
            "- brain_track_concept(name) / brain_save_note(title, content, tags)\n"
            "- create_plan(title, phases)\n"
            "- list_agent_types() / get_team_manifest()\n"
            "- create_agent_type(name, instructions, description)\n\n"
            "Delegation tools (use ONLY for complex sub-tasks):\n"
            "- delegate_to_agent(agent_type, task) — run a specialized sub-agent\n\n"
            "## RULES\n"
            "- Prefer direct tools when possible (brain_search, verify_links)\n"
            "- Use delegate_to_agent ONLY for steps needing external research/scraping/analysis\n"
            "- store_result + load_result after every tool call\n"
            "- FINAL OUTPUT: raw data only, no thinking/planning narrative"
        ),
        model=model,
        tools=[
            list_agent_types,
            get_team_manifest,
            create_agent_type,
            delegate_to_agent,
            store_result,
            load_result,
            list_results,
            store_context,
            load_context,
            verify_links,
            create_plan,
            brain_search,
            brain_track_concept,
            brain_save_note,
        ],
    )


def _is_function_call(delta: str) -> bool:
    """Check if a text delta is a JSON function call (not user-visible)."""
    stripped = delta.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return True
    if stripped.startswith('{"') and ('":"' in stripped or '":' in stripped):
        return True
    return False


def _requires_tool_use(task: str) -> bool:
    markers = [
        "delegate_to_agent",
        "store_result",
        "raw data",
        "execute each step",
        "current web data",
    ]
    lowered = task.lower()
    return any(marker in lowered for marker in markers)


async def run_planner(task: str, max_turns: int = 25) -> str:
    agent = await create_planner_agent()
    print(f"  ⚙ Planner thinking...")
    result = Runner.run_streamed(agent, task, max_turns=max_turns)
    chunks = []
    tool_calls = 0
    async for event in result.stream_events():
        if event.type == "raw_response_event" and hasattr(event.data, "delta"):
            delta = event.data.delta
            if delta and not _is_function_call(delta):
                print(delta, end="", flush=True)
                chunks.append(delta)
        elif event.type == "agent_updated_stream_event":
            print(f"\n  ⚙ → {event.new_agent.name} speaking...\n", flush=True)
        elif event.type == "run_item_stream_event" and event.name == "tool_called":
            tool_calls += 1
    print(f"\n  ⚙ Planner finished")
    final_output = result.final_output if result.final_output is not None else "".join(chunks)
    if _requires_tool_use(task) and tool_calls == 0:
        warning = (
            "\n\n=== EXECUTION FAILURE ===\n"
            "Planner completed without making any tool calls. This indicates the active local "
            "model did not follow the tool-calling contract for an execution task."
        )
        print(warning)
        final_output = f"{final_output}{warning}"
    return str(final_output)
