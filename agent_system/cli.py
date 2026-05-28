#!/usr/bin/env python
"""CLI entrypoint for the agent system."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import Runner
from agents.mcp import MCPServerStdio


async def run_general(agent_type: str):
    from agent_system.registry import get_agent
    from agent_system.base import create_agent_from_definition

    definition = get_agent(agent_type)
    if not definition:
        print(f"Agent type '{agent_type}' not found. Available:")
        from agent_system.registry import list_agents
        for a in list_agents():
            print(f"  - {a['name']}: {a.get('description', '')}")
        return

    async with MCPServerStdio(
        name="Scrapling",
        params={"command": "scrapling", "args": ["mcp"]},
        cache_tools_list=True,
    ) as scrapling:
        agent = await create_agent_from_definition(
            definition=definition,
            extra_mcp_servers=[scrapling],
        )
        print(f" {agent_type} agent ready  (Scrapling + Trends + opnbrain)\n")
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


async def single_general(agent_type: str, task: str):
    from agent_system.registry import get_agent
    from agent_system.base import create_agent_from_definition

    definition = get_agent(agent_type)
    if not definition:
        print(f"Agent type '{agent_type}' not found.")
        return

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
        print(result.final_output)


async def single_orchestrator(task: str):
    from agent_system.orchestrator_agent import run_orchestrator
    result = await run_orchestrator(task)
    print(result)


async def interactive_orchestrator():
    from agent_system.orchestrator_agent import run_orchestrator
    print(" Orchestrator Agent  (manages agent registry + delegates)\n")
    try:
        while True:
            prompt = input(">>> ").strip()
            if not prompt:
                continue
            if prompt.lower() in ("quit", "exit", "q"):
                break
            result = await run_orchestrator(prompt)
            print(f"\n{result}\n")
    except KeyboardInterrupt:
        print()


async def list_agents():
    from agent_system.registry import list_agents
    agents = list_agents()
    if not agents:
        print("No agent types registered.")
        return
    print("Registered Agent Types:")
    for a in agents:
        premade = " (premade)" if a.get("is_premade") else ""
        print(f"  {a['name']}{premade}: {a.get('description', '')}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent System CLI")
    parser.add_argument(
        "mode", nargs="?", default="list",
        choices=["list", "general", "orchestrator", "g", "o"],
        help="list=show agents, general=run an agent, orchestrator=run orchestrator",
    )
    parser.add_argument("args", nargs="*", help="agent_type query... for general, or query for orchestrator")
    args = parser.parse_args()

    mode = args.mode
    if mode == "g":
        mode = "general"
    elif mode == "o":
        mode = "orchestrator"

    if mode == "list":
        asyncio.run(list_agents())
        return

    if mode == "orchestrator":
        query = " ".join(args.args) if args.args else None
        if query:
            asyncio.run(single_orchestrator(query))
        else:
            asyncio.run(interactive_orchestrator())
        return

    if mode == "general":
        if not args.args:
            print("Usage: start-agent.sh general <agent_type> [query...]")
            print("       start-agent.sh general research 'your topic'")
            print("       start-agent.sh general coder 'write a function'")
            return
        agent_type = args.args[0]
        query = " ".join(args.args[1:]) if len(args.args) > 1 else None
        if query:
            asyncio.run(single_general(agent_type, query))
        else:
            asyncio.run(run_general(agent_type))
        return


if __name__ == "__main__":
    main()
