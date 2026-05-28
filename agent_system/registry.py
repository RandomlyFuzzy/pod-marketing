"""Agent registry — loads/saves agent definitions as JSON files."""
import json
import os
import time
from pathlib import Path

DEFINITIONS_DIR = Path(__file__).parent / "definitions"
os.makedirs(DEFINITIONS_DIR, exist_ok=True)

# Immutable core — every agent gets these automatically
CORE_MCP_SERVERS = ["scrapling"]
CORE_TOOLS = [
    "check_trends",
    "validate_with_trends",
    "brain_save_note",
    "brain_track_concept",
    "brain_search",
    "brain_publish_summary",
]

TOOL_DESCRIPTIONS = {
    "check_trends": "Google Trends interest check",
    "validate_with_trends": "Compare demand for a product idea and related terms",
    "delegate_to_agent": "Run a registered sub-agent on a task",
    "create_agent_type": "Create a new custom agent definition",
    "brain_save_note": "Save a note to persistent brain memory",
    "brain_track_concept": "Register a concept in brain memory",
    "brain_search": "Search persistent brain memory",
    "brain_publish_summary": "Publish a structured brain summary",
}

MCP_TOOL_DESCRIPTIONS = {
    "scrapling": [
        "get",
        "fetch",
        "stealthy_fetch",
        "bulk_get",
        "bulk_fetch",
        "screenshot",
    ],
}


def _path(name: str) -> Path:
    slug = name.lower().replace(" ", "_").replace("-", "_")
    return DEFINITIONS_DIR / f"{slug}.json"


def list_agents() -> list[dict]:
    agents = []
    for fpath in sorted(DEFINITIONS_DIR.glob("*.json")):
        try:
            data = json.loads(fpath.read_text())
            data["file"] = fpath.name
            agents.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return agents


def effective_tools(definition: dict) -> dict:
    """Return the function and MCP tools an agent is configured to receive."""
    function_tools = definition.get("tools", CORE_TOOLS)
    mcp_servers = definition.get("mcp_servers", CORE_MCP_SERVERS)
    mcp_tools = []
    for server in mcp_servers:
        mcp_tools.extend(MCP_TOOL_DESCRIPTIONS.get(server, []))
    return {
        "function_tools": sorted(set(function_tools)),
        "mcp_servers": sorted(set(mcp_servers)),
        "mcp_tools": sorted(set(mcp_tools)),
    }


def team_manifest() -> str:
    """Human-readable registry summary for planners and diagnostics."""
    lines = ["Registered team/agent capabilities:"]
    for agent in list_agents():
        tools = effective_tools(agent)
        function_tools = ", ".join(tools["function_tools"]) or "none"
        mcp_tools = ", ".join(tools["mcp_tools"]) or "none"
        lines.append(
            f"- {agent['name']}: {agent.get('description', '')}\n"
            f"  model: {agent.get('model', 'default')}\n"
            f"  function tools: {function_tools}\n"
            f"  MCP tools: {mcp_tools}"
        )
    return "\n".join(lines)


def get_agent(name: str) -> dict | None:
    fpath = _path(name)
    if not fpath.exists():
        for p in DEFINITIONS_DIR.glob("*.json"):
            try:
                data = json.loads(p.read_text())
                if data.get("name", "").lower() == name.lower():
                    data["file"] = p.name
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return None
    try:
        data = json.loads(fpath.read_text())
        data["file"] = fpath.name
        return data
    except (json.JSONDecodeError, OSError):
        return None


def create_agent(
    name: str,
    instructions: str,
    description: str = "",
    is_premade: bool = False,
) -> dict:
    if get_agent(name):
        raise ValueError(f"Agent '{name}' already exists")
    data = {
        "name": name,
        "description": description or f"Agent: {name}",
        "instructions": instructions,
        "is_premade": is_premade,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }
    fpath = _path(name)
    fpath.write_text(json.dumps(data, indent=2))
    data["file"] = fpath.name
    return data


def update_agent(name: str, updates: dict) -> dict | None:
    existing = get_agent(name)
    if not existing:
        return None
    existing.update(updates)
    existing.pop("file", None)
    fpath = _path(name)
    fpath.write_text(json.dumps(existing, indent=2))
    existing["file"] = fpath.name
    return existing


def delete_agent(name: str) -> bool:
    fpath = _path(name)
    if fpath.exists():
        fpath.unlink()
        return True
    for p in DEFINITIONS_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text())
            if data.get("name", "").lower() == name.lower():
                p.unlink()
                return True
        except (json.JSONDecodeError, OSError):
            pass
    return False


def resolve_instructions(definition: dict) -> str:
    # Determine which tools this agent actually has access to
    if "tools" in definition:
        # Get Scrapling tools description if scrapling MCP is included
        scrapling_tools = ""
        if "mcp_servers" not in definition or "scrapling" in definition.get("mcp_servers", []):
            scrapling_tools = (
                "- `get`, `fetch`, `stealthy_fetch`, `bulk_get`, `bulk_fetch`, `screenshot` — Scrapling web tools\n"
            )
        
        # Build the tools list
        tools_list = []
        if scrapling_tools:
            tools_list.append(scrapling_tools.strip())
        
        for tool_name in definition["tools"]:
            if tool_name in TOOL_DESCRIPTIONS:
                tools_list.append(f"- `{tool_name}` — {TOOL_DESCRIPTIONS[tool_name]}")
        
        tools_section = "CORE TOOLS available to you:\n" + "\n".join(tools_list) + "\n\n" if tools_list else ""
    else:
        # Default to all core tools (backward compatibility)
        tools_section = (
            "CORE TOOLS available to you (always present):\n"
            "- `get`, `fetch`, `stealthy_fetch`, `bulk_get`, `bulk_fetch`, `screenshot` — Scrapling web tools\n"
            "- `check_trends(keywords, ...)` — Google Trends interest check\n"
            "- `validate_with_trends(product_idea, ...)` — compare demand\n"
            "- `delegate_to_agent(agent_type, task)` — OFFLOAD work to a sub-agent\n"
            "- `create_agent_type(name, instructions, description)` — create a custom sub-agent\n"
            "- `brain_save_note(title, content, tags)` — save to brain memory\n"
            "- `brain_track_concept(name)` — register a concept\n"
            "- `brain_search(query)` — search brain memory\n"
            "- `brain_publish_summary(name, content, tags)` — create reference summary\n\n"
        )

    base = (
        "You are a specialized agent. Follow your instructions carefully.\n\n"
        f"{tools_section}"
        "OFFLOADING RULE: If a task is mechanical, repetitive, or not core to your current goal "
        "(like parsing a large document for one fact, running a quick search, or cross-checking data), "
        "call `delegate_to_agent` to offload it. This keeps you focused on high-value work.\n"
        "If no existing agent type fits, use `create_agent_type` first to make a custom helper.\n\n"
    )
    custom = definition.get("instructions", "")
    return base + custom
