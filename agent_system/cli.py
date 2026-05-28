#!/usr/bin/env python
"""CLI entrypoint for the agent system.

All execution goes through the orchestrator. Planner, reviewer, and specialist
agents remain internal components used by the orchestrator/delegation layer.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def list_agents() -> None:
    from agent_system.registry import team_manifest

    print(team_manifest())


async def run_goal(goal: str) -> None:
    from agent_system.orchestrator_agent import run_orchestrator

    result = await run_orchestrator(goal)
    print(result)


async def interactive_orchestrator() -> None:
    print(" Orchestrator Agent  (all work is routed through planner, agents, reviewer)\n")
    try:
        while True:
            prompt = input(">>> ").strip()
            if not prompt:
                continue
            if prompt.lower() in ("quit", "exit", "q"):
                break
            await run_goal(prompt)
    except KeyboardInterrupt:
        print()


def _compat_goal(mode: str, args: list[str]) -> str | None:
    """Translate old direct-agent CLI shapes into orchestrator goals."""
    if mode in ("list", "ls"):
        return None

    if mode in ("orchestrator", "o"):
        return " ".join(args).strip()

    if mode in ("planner", "p"):
        task = " ".join(args).strip()
        return task or ""

    if mode in ("reviewer", "r"):
        task = " ".join(args).strip()
        return f"Review this through the normal orchestrator quality loop: {task}" if task else ""

    if mode in ("general", "g"):
        if not args:
            return ""
        agent_type = args[0]
        task = " ".join(args[1:]).strip()
        if task:
            return f"Use the orchestrator and delegate to `{agent_type}` if appropriate: {task}"
        return f"Start an orchestrated session using `{agent_type}` as the likely specialist."

    from agent_system.registry import get_agent

    task = " ".join(args).strip()
    if get_agent(mode):
        if task:
            return f"Use the orchestrator and delegate to `{mode}` if appropriate: {task}"
        return f"Start an orchestrated session using `{mode}` as the likely specialist."

    return " ".join([mode] + args).strip()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Agent System CLI")
    parser.add_argument(
        "mode",
        nargs="?",
        default="list",
        help="list=show agents, orchestrator [goal]=run the orchestrator. Legacy direct-agent modes are routed through the orchestrator.",
    )
    parser.add_argument("args", nargs="*", help="goal text")
    args = parser.parse_args()

    goal = _compat_goal(args.mode, args.args)
    if goal is None:
        asyncio.run(list_agents())
        return

    if goal:
        asyncio.run(run_goal(goal))
    else:
        asyncio.run(interactive_orchestrator())


if __name__ == "__main__":
    main()
