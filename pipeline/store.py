"""In-memory session store for pipeline state.
In production, replace with a database."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / ".pipeline_data"
DATA_DIR.mkdir(exist_ok=True)


def _path(session_id: str) -> Path:
    return DATA_DIR / f"{session_id}.json"


def get_state(session_id: str) -> dict:
    p = _path(session_id)
    if p.exists():
        return json.loads(p.read_text())
    return {
        "phase": "research",
        "niche": "",
        "niche_description": "",
        "products": [],
        "current_product": None,
        "listing_content": None,
        "research_data": None,
        "validation_data": None,
        "publish_data": None,
        "history": [],
    }


def save_state(session_id: str, state: dict):
    _path(session_id).write_text(json.dumps(state, indent=2, default=str))


def append_history(session_id: str, entry: dict):
    state = get_state(session_id)
    state.setdefault("history", []).append(entry)
    save_state(session_id, state)
