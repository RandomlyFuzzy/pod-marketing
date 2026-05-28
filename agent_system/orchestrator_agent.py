"""Orchestrator agent — plans work, delegates to General Agent, synthesizes results."""
import os

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_key
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from agent_system.opnbrain import save_conversation, publish_concept, search_brain

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b-128k")


@function_tool
async def delegate_to_general_agent(task: str) -> str:
    """Pass a task to the General Agent for execution.
    
    The General Agent has access to:
    - Scrapling (web scraping / searching)
    - Google Trends (market demand validation)
    - opnbrain brain (persistent memory)
    
    Use this to delegate research, analysis, content creation, or any hands-on work.
    
    Args:
        task: Clear, detailed instructions for the General Agent
    """
    from agent_system.general_agent import create_general_agent
    from agents.mcp import MCPServerStdio

    async with MCPServerStdio(
        name="Scrapling",
        params={"command": "scrapling", "args": ["mcp"]},
        cache_tools_list=True,
    ) as scrapling:
        agent = await create_general_agent(scrapling_server=scrapling)
        result = await Runner.run(
            agent,
            task,
            max_turns=12,
        )
        return result.final_output


@function_tool
async def brain_save_note(
    title: str,
    content: str,
    tags: list[str] | str | None = None,
) -> str:
    """Save a note or conversation to the brain for persistent memory.
    
    Use this to log the overall plan, intermediate decisions, and final synthesis.
    
    Args:
        title: Short descriptive title (3-8 words)
        content: The note body in markdown
        tags: Optional category tags (comma-separated string or list)
    """
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    path = save_conversation(
        title=title,
        model=OLLAMA_MODEL,
        tags=tags or [],
        is_chat=False,
        prompt="",
        response=content,
    )
    return f"Saved to brain: {path}"


@function_tool
async def brain_track_concept(name: str) -> str:
    """Register a concept in the brain so it gets a wiki page."""
    path = publish_concept(name)
    return f"Concept tracked: {path}" if path else f"Skipped (bad name: {name!r})"


@function_tool
async def brain_search(query: str) -> str:
    """Search the brain's memory for past notes and concepts."""
    return search_brain(query)


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
            "You are an orchestrator agent. Your job is to:\n"
            "1. Receive a high-level request from the user\n"
            "2. Break it down into clear subtasks\n"
            "3. Delegate each subtask to the General Agent via `delegate_to_general_agent`\n"
            "4. Synthesize the results into a cohesive final output\n"
            "5. Log everything to the brain via `brain_save_note` and `brain_track_concept`\n\n"
            "YOUR TOOLS (use these exact names with named parameters):\n"
            "- `delegate_to_general_agent(task=\"...\")` — sends a task to the General Agent\n"
            "- `brain_save_note(title=\"...\", content=\"...\", tags=[...])` — saves to brain\n"
            "- `brain_track_concept(name=\"...\")` — registers concepts\n"
            "- `brain_search(query=\"...\")` — checks what's already in the brain\n\n"
            "WORKFLOW:\n"
            "1. Check the brain first with `brain_search` to see if similar work exists\n"
            "2. Break the request into subtasks (research, analyze, create, etc.)\n"
            "3. For each subtask, call `delegate_to_general_agent` with clear instructions\n"
            "4. Track key concepts with `brain_track_concept`\n"
            "5. After all subtasks complete, synthesize everything\n"
            "6. Save the final synthesis to brain with `brain_save_note`\n"
            "7. Present the final result to the user\n\n"
            "CRITICAL: Do NOT make up tool names. Only use the tools listed above.\n"
            "Call tools with named parameters (e.g. `delegate_to_general_agent(task=\"...\")`).\n\n"
            "Be thorough — break complex requests into multiple delegations rather than "
            "one huge task. Track every major concept that appears."
        ),
        model=model,
        tools=[
            delegate_to_general_agent,
            brain_save_note,
            brain_track_concept,
            brain_search,
        ],
    )
