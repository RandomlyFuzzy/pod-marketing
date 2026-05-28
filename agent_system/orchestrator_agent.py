"""Orchestrator agent — uses registry directly to delegate to specialized agents."""
import os
import sys

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_key
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from .opnbrain import save_conversation, publish_concept, search_brain
from .registry import list_agents, get_agent, create_agent, CORE_MCP_SERVERS, CORE_TOOLS

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b-128k")


@function_tool
async def brain_save_note(title: str, content: str, tags: list[str] | str | None = None) -> str:
    """Save a note or conversation to the brain.
    
    Args:
        title: Short descriptive title (3-8 words)
        content: The note body in markdown
        tags: Optional category tags (comma-separated string or list)
    """
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
    """List all registered agent types available for delegation."""
    agents = list_agents()
    if not agents:
        return "No agent types registered."
    lines = ["Registered Agent Types:"]
    for a in agents:
        premade = "(premade)" if a.get("is_premade") else ""
        lines.append(f"- {a['name']} {premade}: {a.get('description', '')}")
    return "\n".join(lines)


@function_tool
async def delegate_to_agent(agent_type: str, task: str) -> str:
    """Create and run a specialized agent with a task.
    
    Each agent type has access to: Scrapling web tools, Google Trends, brain memory.
    Available agent types can be listed with list_agent_types.
    
    Args:
        agent_type: The type of agent to run (e.g. research, scourer, coder, idea_generator, product_producer, email_reader)
        task: Clear, detailed task description for the agent
    """
    from .base import create_agent_from_definition

    definition = get_agent(agent_type)
    if not definition:
        types = [a["name"] for a in list_agents()]
        return f"Agent type '{agent_type}' not found. Available: {', '.join(types)}"

    python = os.environ.get("AGENT_MANAGER_PYTHON", sys.executable)
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


def _make_ollama_client():
    return AsyncOpenAI(
        base_url=f"{OLLAMA_URL}/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
    )


async def create_orchestrator_agent() -> Agent:
    client = _make_ollama_client()
    model = OpenAIChatCompletionsModel(model=OLLAMA_MODEL, openai_client=client)
    set_default_openai_key("ollama")

    return Agent(
        name="OrchestratorAgent",
        instructions=(
            "You are an orchestrator agent that manages a registry of specialized agents.\n\n"
            "YOUR WORKFLOW:\n"
            "1. Receive a high-level request from the user\n"
            "2. Check the brain with `brain_search` for prior context\n"
            "3. Break the request into subtasks\n"
            "4. For each subtask, pick the right agent type and call `delegate_to_agent`\n"
            "5. Track concepts with `brain_track_concept`\n"
            "6. Save final synthesis with `brain_save_note`\n\n"
            "AVAILABLE AGENT TYPES (use list_agent_types to see all):\n"
            "- research: deep topic investigation (Scrapling + Trends)\n"
            "- scourer: broad data collection from multiple sources\n"
            "- idea_generator: creative ideation from brain knowledge\n"
            "- product_producer: product listing creation\n"
            "- coder: code writing and analysis\n"
            "- email_reader: email summarization\n"
            "- planner: multi-phase planning with subagent creation\n"
            "- reviewer: quality review with structured feedback\n\n"
            "YOUR TOOLS:\n"
            "- `list_agent_types()` — show all registered agents\n"
            "- `delegate_to_agent(agent_type, task)` — run a specialized agent\n"
            "- `brain_search(query)` — search memory\n"
            "- `brain_track_concept(name)` — track concepts\n"
            "- `brain_save_note(title, content, tags)` — save notes\n\n"
            "CRITICAL RULES:\n"
            "- For each subtask, you MUST actually call `delegate_to_agent`.\n"
            "  Do not just say you will — invoke the tool.\n"
            "- Use named params: delegate_to_agent(agent_type=\"research\", task=\"...\")\n"
            "- After delegation, synthesize results and save to brain."
        ),
        model=model,
        tools=[
            list_agent_types,
            delegate_to_agent,
            brain_save_note,
            brain_track_concept,
            brain_search,
        ],
    )


async def run_orchestrator(task: str, max_turns: int = 20) -> str:
    agent = await create_orchestrator_agent()
    result = await Runner.run(agent, task, max_turns=max_turns)
    return result.final_output
