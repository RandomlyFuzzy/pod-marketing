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
    base = (
        "You are a specialized agent. Follow your instructions carefully.\n\n"
        "CORE TOOLS available to you (always present):\n"
        "- `get`, `fetch`, `stealthy_fetch`, `bulk_get`, `bulk_fetch`, `screenshot` — Scrapling web tools\n"
        "- `check_trends(keywords, ...)` — Google Trends interest check\n"
        "- `validate_with_trends(product_idea, ...)` — compare demand\n"
        "- `brain_save_note(title, content, tags)` — save to brain memory\n"
        "- `brain_track_concept(name)` — register a concept\n"
        "- `brain_search(query)` — search brain memory\n"
        "- `brain_publish_summary(name, content, tags)` — create reference summary\n\n"
    )
    custom = definition.get("instructions", "")
    return base + custom
