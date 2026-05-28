"""MCP server for managing agent definitions (CRUD + delegation)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent
import mcp.server.stdio

from agent_system.registry import (
    list_agents,
    get_agent,
    create_agent,
    update_agent,
    delete_agent,
    CORE_MCP_SERVERS,
    CORE_TOOLS,
)
from agent_system.base import create_agent_from_definition
from agents import Runner
from agents.mcp import MCPServerStdio

server = Server("agent-manager")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_agent_types",
            description="List all registered agent types",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_agent_definition",
            description="Get a specific agent type's definition",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Agent type name"}
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="create_agent_type",
            description="Create a new agent type",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique agent name"},
                    "instructions": {"type": "string", "description": "System instructions for the agent"},
                    "description": {"type": "string", "description": "Brief description"},
                },
                "required": ["name", "instructions"],
            },
        ),
        Tool(
            name="update_agent_type",
            description="Update an existing agent type's definition",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Agent type name"},
                    "instructions": {"type": "string", "description": "New instructions"},
                    "description": {"type": "string", "description": "New description"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="delete_agent_type",
            description="Delete an agent type definition",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Agent type name"}
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="delegate_to_agent",
            description="Create and run an agent of the given type with a task",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_type": {"type": "string", "description": "Agent type name (e.g. research, scourer, coder)"},
                    "task": {"type": "string", "description": "Task description for the agent"},
                },
                "required": ["agent_type", "task"],
            },
        ),
        Tool(
            name="get_core_info",
            description="List immutable core MCP servers and tools shared by all agents",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "list_agent_types":
        agents = list_agents()
        if not agents:
            return [TextContent(type="text", text="No agent types registered.")]
        lines = ["## Registered Agent Types\n"]
        for a in agents:
            premade = " (premade)" if a.get("is_premade") else ""
            lines.append(f"- **{a['name']}**{premade}: {a.get('description', '')}")
        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "get_agent_definition":
        agent = get_agent(arguments["name"])
        if not agent:
            return [TextContent(type="text", text=f"Agent '{arguments['name']}' not found.")]
        import json
        return [TextContent(type="text", text=json.dumps(agent, indent=2))]

    elif name == "create_agent_type":
        try:
            agent = create_agent(
                name=arguments["name"],
                instructions=arguments["instructions"],
                description=arguments.get("description", ""),
            )
            return [TextContent(type="text", text=f"Agent '{agent['name']}' created.")]
        except ValueError as e:
            return [TextContent(type="text", text=str(e))]

    elif name == "update_agent_type":
        updates = {}
        if "instructions" in arguments:
            updates["instructions"] = arguments["instructions"]
        if "description" in arguments:
            updates["description"] = arguments["description"]
        result = update_agent(arguments["name"], updates)
        if not result:
            return [TextContent(type="text", text=f"Agent '{arguments['name']}' not found.")]
        return [TextContent(type="text", text=f"Agent '{arguments['name']}' updated.")]

    elif name == "delete_agent_type":
        ok = delete_agent(arguments["name"])
        return [TextContent(type="text", text=f"Deleted: {ok}")]

    elif name == "get_core_info":
        return [TextContent(
            type="text",
            text=(
                "## Immutable Core\n\n"
                f"**MCP Servers:** {', '.join(CORE_MCP_SERVERS)}\n"
                f"**Tools:** {', '.join(CORE_TOOLS)}\n\n"
                "These cannot be modified through the management interface."
            ),
        )]

    elif name == "delegate_to_agent":
        agent_type = arguments["agent_type"]
        task = arguments["task"]
        definition = get_agent(agent_type)
        if not definition:
            return [TextContent(
                type="text",
                text=f"Agent type '{agent_type}' not found. Use create_agent_type first or pick from: "
                     f"{', '.join(a['name'] for a in list_agents())}",
            )]
        try:
            result = await _run_delegated(definition, task)
            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"Delegation error: {e}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _run_delegated(definition: dict, task: str) -> str:
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


# Note: long-running delegation calls may timeout on the MCP client side.
# For reliable delegation, use the orchestrator agent (Python API) directly.


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="agent-manager",
                server_version="0.1.0",
                capabilities={},
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
