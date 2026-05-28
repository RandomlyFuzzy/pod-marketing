"""Planner agent — plans complex work, creates subagents, delegates, and tracks progress."""
import os
import sys

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_key
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from .opnbrain import save_conversation, publish_concept, search_brain
from .registry import create_agent, get_agent, list_agents, delete_agent

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
async def create_plan(title: str, phases: str) -> str:
    """Create and save a multi-phase plan to the brain.
    
    Args:
        title: Plan title
        phases: Newline-separated phase definitions. Each line: "Phase N | Name | AgentType | Goal" 
    """
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
    for phase in phases:
        publish_concept(phase.get("name", ""))
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

    return Agent(
        name="PlannerAgent",
        instructions=(
            "You are a planner agent. Your job is to break complex goals into manageable phases, "
            "create specialized subagents for each phase, delegate the work, and track progress.\n\n"
            "YOUR WORKFLOW:\n"
            "1. Receive a high-level goal from the user\n"
            "2. Check the brain with `brain_search` for prior context\n"
            "3. Break the goal into phases — each phase should have a clear purpose\n"
            "4. For each phase that needs a specialist, call `create_agent_type` to make a "
            "custom subagent with precise instructions for that specific task\n"
            "5. Call `create_plan` to save the full plan to the brain\n"
            "6. Execute each phase by calling `delegate_to_agent` with the right subagent\n"
            "7. Track key concepts with `brain_track_concept`\n"
            "8. After all phases complete, synthesize and save final results with `brain_save_note`\n\n"
            "YOUR TOOLS:\n"
            "- `list_agent_types()` — see available agents\n"
            "- `create_agent_type(name, instructions, description)` — create a custom subagent\n"
            "- `delegate_to_agent(agent_type, task)` — run a subagent\n"
            "- `create_plan(title, phases)` — save a plan (phases is newline-separated: \"Name | AgentType | Goal\")\n"
            "- `brain_search(query)` — search memory\n"
            "- `brain_track_concept(name)` — track concepts\n"
            "- `brain_save_note(title, content, tags)` — save notes\n\n"
            "CRITICAL RULES:\n"
            "- Create subagents with specific, focused instructions for each phase\n"
            "- After creating a subagent, delegate to it immediately\n"
            "- Track every major concept that appears\n"
            "- Save the plan BEFORE executing phases\n"
            "- Synthesize all phase results into a final summary\n"
            "- Use named params: create_agent_type(name=\"...\", instructions=\"...\")\n"
            "- For create_plan: create_plan(title=\"My Plan\", phases=\"PhaseName | agent_type | goal\\nPhase2 | ...\")"
        ),
        model=model,
        tools=[
            list_agent_types,
            create_agent_type,
            delegate_to_agent,
            create_plan,
            brain_search,
            brain_track_concept,
            brain_save_note,
        ],
    )


async def run_planner(task: str, max_turns: int = 25) -> str:
    agent = await create_planner_agent()
    result = await Runner.run(agent, task, max_turns=max_turns)
    return result.final_output
