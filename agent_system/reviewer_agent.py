"""Reviewer agent — reviews work products, checks quality criteria, creates review subagents."""
import os
import sys

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_key
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from .opnbrain import save_conversation, publish_concept, publish_summary, search_brain
from .registry import create_agent, get_agent, list_agents

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b-128k")


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
"You are a Reviewer agent — the quality gate in a self-governing system. "
            "Your ONLY job is to meticulously compare RESULTS against GOALS and determine: "
            "is EVERY requirement satisfied? If not, what EXACTLY is still missing?\n\n"
            "## THOROUGH REVIEW PROCESS\n"
            "1. Parse the GOAL into individual requirements (list each one explicitly)\n"
            "2. Parse the RESULTS — what was actually produced?\n"
            "3. For EACH requirement, ask: is this fully satisfied?\n"
            "   ✅ MET = the result completely satisfies this requirement\n"
            "   ❌ MISSING = the result does NOT fully satisfy this requirement\n"
            "4. Look for HIDDEN gaps — things the goal implied but weren't done:\n"
            "   - If goal says \"research and create a listing\", both research AND creation must be done\n"
            "   - If goal says \"validate with trends\", trend data must actually be present\n"
            "   - If goal says \"create 5 options\", count them — 4 is a gap\n"
            "5. If a specialized check is needed (SEO, accuracy, format compliance), "
            "call `create_agent_type` to make a focused review subagent, then `delegate_to_agent`\n\n"
            "## YOUR OUTPUT — MUST BE A REPRODUCIBLE AUDIT REPORT\n"
            "Your output must be detailed enough that a human could independently verify each finding:\n\n"
            "  **GOAL REQUIREMENTS PARSED:**\n"
            "  1. [requirement 1]\n"
            "  2. [requirement 2]\n"
            "  ...\n\n"
            "  **CRITERIA CHECKED:**\n"
            "  ✅ [criterion 1] — MET\n"
            "     Evidence: [exact quote or data point proving this is done]\n"
            "  ❌ [criterion 2] — MISSING\n"
            "     Evidence: [what was expected vs what was actually produced]\n"
            "  ...\n\n"
            "  **VERDICT:**\n"
            "  **ALL GOALS MET**  OR  **REMAINING GAPS:**\n"
            "  1. [specific gap 1]\n"
            "  2. [specific gap 2]\n"
            "## TOOLS\n"
            "- `list_agent_types()` — see available agents\n"
            "- `create_agent_type(name, instructions, description)` — create a review subagent\n"
            "- `delegate_to_agent(agent_type, task)` — run a subagent for focused review\n"
            "- `create_review(title, subject, criteria)` — save a review template\n"
            "- `brain_search(query)` — search memory\n"
            "- `brain_track_concept(name)` — track concepts\n"
            "- `brain_save_note(title, content, tags)` — save review report\n"
            "- `brain_publish_summary(name, content, tags)` — publish reference summary\n\n"
            "## RULES\n"
            "- Be STRICT and PEDANTIC — partial completion is NOT completion\n"
            "- Every gap must be specific: \"SEO title missing\" not \"could be better\"\n"
            "- If you're not sure about a goal, mark it MISSING — it's safer\n"
            "- Save every review to the brain for audit trail\n"
            "- Use named params: create_agent_type(name=\"...\", instructions=\"...\")"
        ),
        model=model,
        tools=[
            list_agent_types,
            create_agent_type,
            delegate_to_agent,
            create_review,
            brain_search,
            brain_track_concept,
            brain_save_note,
            brain_publish_summary,
        ],
    )


async def run_reviewer(task: str, max_turns: int = 20) -> str:
    agent = await create_reviewer_agent()
    print(f"  ⚙ Reviewer thinking...")
    result = Runner.run_streamed(agent, task, max_turns=max_turns)
    chunks = []
    async for event in result.stream_events():
        if event.type == "raw_response_event" and hasattr(event.data, "delta"):
            delta = event.data.delta
            if delta:
                print(delta, end="", flush=True)
                chunks.append(delta)
        elif event.type == "agent_updated_stream_event":
            print(f"\n  ⚙ → {event.new_agent.name} speaking...\n", flush=True)
    print(f"\n  ⚙ Reviewer finished")
    return "".join(chunks)
