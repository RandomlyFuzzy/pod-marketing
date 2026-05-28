"""CLI entrypoint for the general research agent."""
import asyncio
import sys
from agents import Runner
from agents.mcp import MCPServerStdio
from .agent import create_agent, research_topic


async def interactive():
    async with MCPServerStdio(
        name="Scrapling",
        params={"command": "scrapling", "args": ["mcp"]},
        cache_tools_list=True,
    ) as scrapling:
        agent = await create_agent(scrapling_server=scrapling)
        print(f"Research Agent ready (Scrapling + Google Trends)\n")
        try:
            while True:
                topic = input("🔍 Research: ").strip()
                if not topic:
                    continue
                if topic.lower() in ("quit", "exit", "q"):
                    break
                result = await Runner.run(agent, topic)
                print(f"\n{result.final_output}\n")
        except KeyboardInterrupt:
            print()


async def single(topic: str):
    result = await research_topic(topic)
    print(result)


def main():
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
        asyncio.run(single(topic))
    else:
        asyncio.run(interactive())


if __name__ == "__main__":
    main()
