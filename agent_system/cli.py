#!/usr/bin/env python
"""CLI entrypoint for the agent system — General Agent and Orchestrator."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import Runner
from agents.mcp import MCPServerStdio


async def run_general():
    from agent_system.general_agent import create_general_agent

    async with MCPServerStdio(
        name="Scrapling",
        params={"command": "scrapling", "args": ["mcp"]},
        cache_tools_list=True,
    ) as scrapling:
        agent = await create_general_agent(scrapling_server=scrapling)
        print(" General Agent ready (Scrapling + Trends + opnbrain)\n")
        try:
            while True:
                prompt = input(">>> ").strip()
                if not prompt:
                    continue
                if prompt.lower() in ("quit", "exit", "q"):
                    break
                result = await Runner.run(agent, prompt, max_turns=12)
                print(f"\n{result.final_output}\n")
        except KeyboardInterrupt:
            print()


async def run_orchestrator():
    from agent_system.orchestrator_agent import create_orchestrator_agent

    agent = await create_orchestrator_agent()
    print(" Orchestrator Agent ready (delegates to General Agent + opnbrain)\n")
    try:
        while True:
            prompt = input(">>> ").strip()
            if not prompt:
                continue
            if prompt.lower() in ("quit", "exit", "q"):
                break
            result = await Runner.run(agent, prompt, max_turns=15)
            print(f"\n{result.final_output}\n")
    except KeyboardInterrupt:
        print()


async def single_general(topic: str):
    from agent_system.general_agent import create_general_agent

    async with MCPServerStdio(
        name="Scrapling",
        params={"command": "scrapling", "args": ["mcp"]},
        cache_tools_list=True,
    ) as scrapling:
        agent = await create_general_agent(scrapling_server=scrapling)
        result = await Runner.run(agent, topic, max_turns=12)
        print(result.final_output)


async def single_orchestrator(topic: str):
    from agent_system.orchestrator_agent import create_orchestrator_agent

    agent = await create_orchestrator_agent()
    result = await Runner.run(agent, topic, max_turns=15)
    print(result.final_output)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run agents")
    parser.add_argument(
        "mode", nargs="?", default="general",
        choices=["general", "orchestrator", "g", "o"],
        help="Agent mode: general (g) or orchestrator (o)",
    )
    parser.add_argument("query", nargs="*", help="Single-shot query (omit for interactive)")
    args = parser.parse_args()

    mode = args.mode
    if mode == "g":
        mode = "general"
    elif mode == "o":
        mode = "orchestrator"

    query = " ".join(args.query) if args.query else None

    if mode == "general":
        if query:
            asyncio.run(single_general(query))
        else:
            asyncio.run(run_general())
    else:
        if query:
            asyncio.run(single_orchestrator(query))
        else:
            asyncio.run(run_orchestrator())


if __name__ == "__main__":
    main()
