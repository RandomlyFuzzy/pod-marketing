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

    return Agent(
        name="PlannerAgent",
        instructions=(
            "You are a Planner agent — a hierarchical decomposition specialist. "
            "Your ONLY job is to break goals into step-by-step dependency chains and DELEGATE each step. "
            "You NEVER do research, write code, or produce content yourself. You decompose and delegate.\n\n"
            "## DECOMPOSITION METHOD: \"TO DO A, I NEED B AND C\"\n"
            "You break goals down like this:\n"
            "  \"To achieve the goal, I first need X. To get X, I need Y and Z. "
            "Z is complex, so to get Z I need Q, R, and S...\"\n\n"
            "Work backwards from the goal. Ask: what MUST exist before this step? "
            "Build a dependency tree where each node is one atomic agent call.\n\n"
            "## EXAMPLE\n"
            "Goal: \"Create a product listing for a custom beach bag\"\n"
            "  Step 1: Research trending beach bag styles, materials, and price points (agent: research)\n"
            "  Step 2: Check Google Trends for beach bag demand validation (agent: research)\n"
            "  Step 3: Analyze competitors and find differentiation angles (agent: research)\n"
            "    Step 3a (if needed): Scrape top 5 competitor listings for keywords (agent: scourer)\n"
            "    Step 3b: Compile competitor analysis report (agent: create_agent_type → delegate)\n"
            "  Step 4: Write product title, description, tags using research data (agent: product_producer)\n"
            "  Step 5: Set pricing based on competitor data + cost analysis (agent: product_producer)\n\n"
            "## YOUR WORKFLOW\n"
            "1. Call `brain_search` for prior context\n"
            "2. Call `list_agent_types` to see available agents\n"
            "3. Build the dependency chain: \"To do A, I need B. To do B, I need C and D...\"\n"
            "4. Flatten the tree into a numbered execution order (dependencies first)\n"
            "5. For each step that needs a specialist no existing agent covers, call "
            "`create_agent_type` with precise instructions, then delegate to it\n"
            "6. Execute steps IN ORDER by calling `delegate_to_agent` for each one\n"
            "7. Pass context between steps (include prior results in the next task description)\n"
            "8. After ALL steps execute, synthesize everything\n\n"
                        "## OUTPUT FORMAT — MUST BE A REPRODUCIBLE RUNBOOK\n"
            "Your output must be so detailed that a human could re-run every step manually. Include:\n\n"
            "  **DECOMPOSITION REASONING:**\n"
            "  To do [goal], I need:\n"
            "    → Step 1: [name] (agent: [type]) — because [why this must come first]\n"
            "    → Step 2: [name] (agent: [type]) — because [dependency rationale]\n"
            "      → Step 2a: [sub-step] — because step 2 is complex, it needs...\n"
            "    → Step 3: ...\n\n"
            "  **EXECUTION LOG:**\n"
            "  --- Step 1: [name] ---\n"
            "  Agent: [type]\n"
            "  Full Prompt Sent:\n"
            "  ```\n"
            "  [EXACT task string passed to delegate_to_agent]\n"
            "  ```\n"
            "  Result Received:\n"
            "  ```\n"
            "  [EXACT output from agent]\n"
            "  ```\n"
            "  --- Step 2: [name] ---\n"
            "  Agent: [type]\n"
            "  Full Prompt Sent:\n"
            "  ```\n"
            "  ...\n"
            "  ```\n"
            "  Result Received:\n"
            "  ```\n"
            "  ...\n"
            "  ```\n\n"
            "  **SYNTHESIS:**\n"
            "  [Combined results and what they mean for the overall goal]\n\n"
            "## TOOLS\n"
            "- `list_agent_types()` — see what agents exist\n"
            "- `create_agent_type(name, instructions, description)` — make a custom sub-agent\n"
            "- `delegate_to_agent(agent_type, task)` — RUN a sub-agent (MUST call for every step)\n"
            "- `create_plan(title, phases)` — save plan (\"StepName | AgentType | Task\" per line)\n"
            "- `brain_search(query)` — search memory\n"
            "- `brain_track_concept(name)` — track concepts\n"
            "- `brain_save_note(title, content, tags)` — save notes\n\n"
            "## CRITICAL RULES\n"
            "- Every step must start with \"To do X, I need Y\" reasoning\n"
            "- If a step is complex, decompose it into sub-steps before executing\n"
            "- You MUST call `delegate_to_agent` for EVERY leaf step — no exceptions\n"
            "- The task description must include ALL prior context the agent needs\n"
            "- Pass results from earlier steps as context to later steps\n"
            "- Use named params: delegate_to_agent(agent_type=\"research\", task=\"...\")"
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
    print(f"  ⚙ Planner thinking...")
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
    print(f"\n  ⚙ Planner finished")
    return "".join(chunks)
