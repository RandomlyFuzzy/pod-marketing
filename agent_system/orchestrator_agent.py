"""Orchestrator — self-governing loop: plan → execute → review → re-plan until all goals are met."""
import os
import sys
import uuid
from datetime import datetime

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_key
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from .opnbrain import save_conversation, publish_concept, search_brain
from .registry import list_agents, get_agent

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b-128k")
OUTPUT_DIR = os.environ.get("AGENT_OUTPUT_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "sessions"))


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
    """Search the brain's memory for past sessions, plans, reviews."""
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
async def log_task_status(session_id: str, step: str, task: str, status: str, detail: str = "") -> str:
    """Log a task's current status to the brain for tracking.
    
    Use this at each stage of the loop to track every task's progress.
    
    Args:
        session_id: Your session identifier
        step: One of: "planned", "delegated", "completed", "needs_rework", "gaps_found", "all_met"
        task: Description of what the task is
        status: Short status like "pending", "in_progress", "done", "needs_replan"
        detail: Optional extra info or context
    """
    tags = ["task-log", f"session-{session_id}", step]
    content = (
        f"## Task Log: {session_id}\n\n"
        f"**Step:** {step}\n"
        f"**Task:** {task}\n"
        f"**Status:** {status}\n"
        f"**Detail:** {detail}\n"
        f"**Timestamp:** iteration\n"
    )
    path = save_conversation(
        title=f"Task {session_id} - {step[:30]}",
        model=OLLAMA_MODEL,
        tags=tags,
        is_chat=False,
        prompt="",
        response=content,
    )
    return f"Task status logged: {path}"


@function_tool
async def delegate_to_agent(agent_type: str, task: str) -> str:
    """Create and run a specialized agent with a task.
    
    IMPORTANT — the agent gets FULL access to Scrapling web tools, Google Trends,
    and brain memory. Give it a detailed, specific task.
    
    Planner and reviewer agents get their full toolkits (subagent creation, planning,
    review templates). Other agents get the core toolkit + Scrapling.
    
    Args:
        agent_type: The type of agent (research, scourer, coder, planner, reviewer,
                    idea_generator, product_producer, email_reader)
        task: Clear, detailed task description
    """
    # Show live progress
    task_preview = task[:120].replace("\n", " ")
    print(f"\n  ▶︎ Delegating to [{agent_type}] agent...")

    # Planner and reviewer have dedicated modules with full toolkits
    if agent_type == "planner":
        from .planner_agent import run_planner
        print(f"    Task: {task_preview}")
        result = await run_planner(task, max_turns=15)
        print(f"  ✓ [{agent_type}] done")
        return result
    elif agent_type == "reviewer":
        from .reviewer_agent import run_reviewer
        print(f"    Task: {task_preview}")
        result = await run_reviewer(task, max_turns=15)
        print(f"  ✓ [{agent_type}] done")
        return result

    # All other agents use the generic definition-based path
    from .base import create_agent_from_definition

    definition = get_agent(agent_type)
    if not definition:
        types = [a["name"] for a in list_agents()]
        return f"Agent type '{agent_type}' not found. Available: {', '.join(types)}"

    print(f"    Task: {task_preview}")
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
        print(f"  ✓ [{agent_type}] done")
        return result.final_output


@function_tool
async def save_outputs(
    session_id: str,
    goal: str,
    plan: str = "",
    execution_log: str = "",
    review_report: str = "",
    final_synthesis: str = "",
    task_log: str = "",
    listing: str = "",
    research_data: str = "",
    analysis_report: str = "",
    additional_files: str = "",
) -> str:
    """Save the full session results to the outputs directory as segmented files.
    
    Call this at the end of a session to persist well-formatted results.
    Creates individual files for each major section plus an index README.
    
    Args:
        session_id: Session identifier
        goal: The original goal
        plan: Planner's decomposition and plan output
        execution_log: Full execution log with per-phase prompts and results
        review_report: Reviewer's verdict and gap analysis
        final_synthesis: Synthesis of all results
        task_log: Task status tracking summary
        listing: Product listing or final deliverable (if applicable)
        research_data: Raw research data and findings (if applicable)
        analysis_report: Analysis or trend report (if applicable)
        additional_files: Extra content as "filename: content" separated by "---FILE---"
    """
    session_dir = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    files = {}

    # README — index / overview
    files["README.md"] = (
        f"# Orchestrator Session: {session_id}\n\n"
        f"**Date:** {timestamp}\n"
        f"**Goal:** {goal}\n\n"
        f"## Contents\n\n"
        f"1. [Plan](plan.md) — task breakdown and decomposition\n"
        + ("2. [Research Data](research.md) — raw findings and trend data\n" if research_data else "")
        + ("3. [Analysis Report](analysis.md) — trend analysis and insights\n" if analysis_report else "")
        + ("4. [Execution Log](execution.md) — per-step prompts and results\n" if execution_log else "")
        + ("5. [Review Report](review.md) — quality gate verdict\n" if review_report else "")
        + ("6. [Product Listing](listing.md) — final deliverable\n" if listing else "")
        + "7. [Synthesis](synthesis.md) — combined results and conclusions\n\n"
        f"---\n*Generated by Orchestrator Self-Governing System*"
    )

    if plan:
        files["plan.md"] = f"# Plan: {session_id}\n\n**Goal:** {goal}\n\n{plan}"
    if research_data:
        files["research.md"] = f"# Research Data\n\n**Session:** {session_id}\n\n{research_data}"
    if analysis_report:
        files["analysis.md"] = f"# Analysis Report\n\n**Session:** {session_id}\n\n{analysis_report}"
    if execution_log:
        files["execution.md"] = f"# Execution Log\n\n**Session:** {session_id}\n\n{execution_log}"
    if review_report:
        files["review.md"] = f"# Review Report\n\n**Session:** {session_id}\n\n{review_report}"
    if listing:
        files["listing.md"] = f"# Product Listing\n\n**Session:** {session_id}\n\n{listing}"
    if final_synthesis:
        files["synthesis.md"] = f"# Synthesis\n\n**Session:** {session_id}\n\n{final_synthesis}"
    if task_log:
        files["tasks.md"] = f"# Task Log\n\n**Session:** {session_id}\n\n{task_log}"

    # Parse additional files
    if additional_files:
        for block in additional_files.split("---FILE---"):
            block = block.strip()
            if not block:
                continue
            if ":" in block:
                fname, _, fcontent = block.partition(":")
                files[fname.strip()] = fcontent.strip()

    written = []
    for fname, fcontent in files.items():
        fpath = os.path.join(session_dir, fname)
        with open(fpath, "w") as f:
            f.write(fcontent)
        written.append(fname)

    # Update latest symlink
    latest_dir = os.path.join(os.path.dirname(OUTPUT_DIR), "latest")
    try:
        if os.path.islink(latest_dir):
            os.unlink(latest_dir)
        os.symlink(session_dir, latest_dir)
    except OSError:
        pass

    return (
        f"Outputs saved to: {session_dir}/ (latest → outputs/latest)\n"
        f"Files written: {', '.join(written)}"
    )


def _make_ollama_client():
    return AsyncOpenAI(
        base_url=f"{OLLAMA_URL}/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
    )


SYSTEM_PROMPT = """You are the Orchestrator — a self-governing agent that autonomously completes complex goals through Plan → Execute → Review → Re-plan iterations.

You delegate ALL actual work to sub-agents. You NEVER do the work yourself — you orchestrate.

Your session_id will be provided in the first message: "Session: <id>". Use this for all log_task_status and save_outputs calls.

Your final output must be a complete runbook that a human could follow to reproduce every step.

## TASK TRACKING — LOG EVERYTHING
You MUST call `log_task_status` at EVERY stage:

1. **After planning** — log each task the planner produced with status "pending"
   `log_task_status(session_id="...", step="planned", task="Step 1: research X", status="pending")`

2. **Before each delegation** — log status "in_progress"
   `log_task_status(session_id="...", step="delegated", task="Step 1: research X", status="in_progress")`

3. **After each delegation** — log status "done"
   `log_task_status(session_id="...", step="completed", task="Step 1: research X", status="done")`

4. **After review** — if gaps found, log them:
   `log_task_status(session_id="...", step="gaps_found", task="[gap description]", status="needs_replan")`

5. **When all goals met** — log final status:
   `log_task_status(session_id="...", step="all_met", task="All goals achieved", status="completed")`

## THE SELF-GOVERNANCE LOOP

You run this loop autonomously until all goals are met:

### 1. PLAN
Call `delegate_to_agent(agent_type="planner", task="...")` to break down your goal.
The planner will produce a step-by-step decomposition with full reasoning and execution log.
Log each planned task with `log_task_status`.
Save the plan to the brain with `brain_save_note`.

### 2. EXECUTE
For EACH phase in the plan, call `delegate_to_agent` with the right agent type.
Give each agent a VERY SPECIFIC task — what to research, what format to output, what questions to answer.
Log each as "in_progress" before delegation and "done" after.
Track all results with `brain_save_note`.

### 3. REVIEW
Call `delegate_to_agent(agent_type="reviewer", task="...")` passing the goal, all results, and asking: are all goals met? What's missing?
The reviewer will return a detailed audit with each criterion checked and evidence.
Log gaps found or all-met status.

### 4. DECIDE
- If **ALL GOALS MET** → save final synthesis to brain, return results to user, DONE.
- If **REMAINING GAPS** exist → feed the gaps back into the planner (GOTO step 1).

The planner will automatically break remaining gaps into finer-grained sub-phases. This recursive decomposition continues until every leaf task is small enough for a specialist agent to complete, and the reviewer confirms everything is satisfied.

## FINAL OUTPUT — REPRODUCIBLE RUNBOOK
When all goals are met, your final output MUST include:

**GOAL:** <original goal>

**ITERATIONS COMPLETED:** <number>

**TASK LOG:**
<summary of all logged tasks and their final statuses>

**FULL EXECUTION LOG:**

For each iteration, include:
- **Iteration N:**
  - **Plan output** (from planner)
  - **Execution results** (per-phase prompts + results)
  - **Review verdict** (criteria + gaps found)
  - **Re-plan input** (if gaps existed)

**FINAL SYNTHESIS:** <combined results>

This must be complete enough that a human could re-run every step manually.

## FINAL OUTPUT — SAVE TO DISK
When all goals are met, you MUST call `save_outputs` to persist results to disk.
Segment the results into separate files by calling save_outputs with each section filled:

```
save_outputs(
    session_id="<your_session_id>",
    goal="<original goal>",
    plan="<full plan output from planner>",
    execution_log="<per-phase prompts and results>",
    review_report="<reviewer verdict and gap analysis>",
    final_synthesis="<combined conclusions>",
    task_log="<task status summary>",
    listing="<if a listing was created>",
    research_data="<if research was done>",
    analysis_report="<if analysis was performed>",
)
```

The system will create: `outputs/sessions/<session_id>/README.md`, `plan.md`, `execution.md`, `review.md`, `synthesis.md`, `tasks.md`, and optionally `listing.md`, `research.md`, `analysis.md`.

## RULES
1. You MUST call `delegate_to_agent` for actual work — do not simulate or fabricate results.
2. Save EVERY intermediate result to the brain for audit trail.
3. Log EVERY task at EVERY stage with `log_task_status`.
4. Track EVERY concept you encounter with `brain_track_concept`.
5. Use `brain_search` at the start to check for prior context.
6. After "ALL GOALS MET", save a final summary and return it to the user.
7. If stuck on a phase, create a more specific sub-plan via the planner rather than guessing.
8. NEVER stop after one iteration if goals remain unmet — keep looping.
9. Give each agent a detailed task with: context, what to produce, format expectations.
10. Your final output must be a complete runbook — every prompt sent and every result received."""


async def create_orchestrator_agent() -> Agent:
    client = _make_ollama_client()
    model = OpenAIChatCompletionsModel(model=OLLAMA_MODEL, openai_client=client)
    set_default_openai_key("ollama")

    return Agent(
        name="OrchestratorAgent",
        instructions=SYSTEM_PROMPT,
        model=model,
        tools=[
            list_agent_types,
            delegate_to_agent,
            log_task_status,
            save_outputs,
            brain_save_note,
            brain_track_concept,
            brain_search,
        ],
    )


async def run_orchestrator(goal: str, max_turns: int = 100) -> str:
    session_id = uuid.uuid4().hex[:8]
    print(f"\n{'='*50}")
    print(f"  Orchestrator — Self-Governing Loop")
    print(f"  Session: {session_id}")
    print(f"  Goal: {goal[:100]}")
    print(f"  Outputs: {os.path.join(OUTPUT_DIR, session_id)}/")
    print(f"{'='*50}")
    agent = await create_orchestrator_agent()
    result = await Runner.run(agent, f"Session: {session_id}\nGoal: {goal}", max_turns=max_turns)
    print(f"{'='*50}")
    return result.final_output
