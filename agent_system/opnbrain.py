"""opnbrain client — persists concepts, notes, and summaries to the brain directory."""
import json
import os
import re
import time
from datetime import date
from pathlib import Path

BRAIN_DIR = Path(os.environ.get("OPNBRAIN_DIR", os.path.expanduser("~/.opnbrain")))

BLACKLIST_PATH = BRAIN_DIR / ".blacklist.json"
META_DIR = BRAIN_DIR / ".meta"
CONVERSATIONS_DIR = BRAIN_DIR / "conversations"
SUMMARIES_DIR = BRAIN_DIR / "summaries"
HNSW_META_PATH = BRAIN_DIR / "hnsw-meta.json"

_WIKI_RE = re.compile(r"\[\[(.+?)\]\]")


def _ensure_dirs():
    for d in [META_DIR, CONVERSATIONS_DIR, SUMMARIES_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def _load_blacklist() -> set[str]:
    if BLACKLIST_PATH.exists():
        return set(json.loads(BLACKLIST_PATH.read_text()))
    return set()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9 .-]", "", name.lower().strip().replace(" ", "-"))


def _wiki_link(name: str) -> str:
    return f"[[{name}]]"


def _extract_wiki_words(text: str) -> list[str]:
    return [w.strip() for w in _WIKI_RE.findall(text) if w.strip()]


def _add_to_hnsw_meta(rel_path: str):
    if HNSW_META_PATH.exists():
        meta = json.loads(HNSW_META_PATH.read_text())
    else:
        meta = []
    if rel_path not in meta:
        meta.append(rel_path)
        HNSW_META_PATH.write_text(json.dumps(meta, indent=2))


def _update_concept_backlinks(concept: str, conv_rel_path: str):
    slug = _slug(concept)
    if not slug:
        return
    fpath = META_DIR / f"{slug}.md"
    blacklist = _load_blacklist()
    if concept.lower() in blacklist or slug in blacklist:
        return
    if fpath.exists():
        content = fpath.read_text()
        appears_section = "## Appears in\n"
        if appears_section in content:
            if conv_rel_path not in content:
                content = content.rstrip() + f"\n- `{conv_rel_path}`\n"
        else:
            content += f"\n{appears_section}\n- `{conv_rel_path}`\n"
    else:
        content = (
            f"# {concept}\n\n"
            f"**Created:** {time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())}\n"
            f"---\n\n"
            f"## Appears in\n\n"
            f"- `{conv_rel_path}`\n"
        )
    fpath.write_text(content)


def _process_wiki_links(body: str, conv_rel_path: str) -> str:
    words = re.findall(r"\b[a-zA-Z][a-zA-Z .-]{2,}\b", body)
    blacklist = _load_blacklist()
    for word in sorted(set(words), key=len, reverse=True):
        slug = _slug(word)
        if not slug or word.lower() in blacklist or slug in blacklist:
            continue
        if slug.isdigit() or len(word) < 3:
            continue
        body = body.replace(word, _wiki_link(word))
        _update_concept_backlinks(word, conv_rel_path)
    return body


def today_dir() -> Path:
    d = CONVERSATIONS_DIR / date.today().isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_conversation(
    title: str,
    model: str = "",
    tags: list[str] | None = None,
    messages: list[dict] | None = None,
    prompt: str = "",
    response: str = "",
    is_chat: bool = True,
) -> str:
    _ensure_dirs()
    tags = tags or []
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    header = (
        f"# {title}\n\n"
        f"**Model:** {model}\n"
        f"**Date:** {now}\n"
        f"**Tags:** {' '.join(_wiki_link(t) for t in tags)}\n\n"
    )

    if is_chat and messages:
        body_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            body_parts.append(f"## {role}\n\n{content}\n")
        body = "\n".join(body_parts)
    else:
        body = f"## user\n\n{prompt}\n\n## assistant\n\n{response}\n"

    slug = _slug(title)[:60]
    fname = f"{slug}.md" if slug else f"note-{int(time.time())}.md"
    rel_path = f"{date.today().isoformat()}/{fname}"
    fpath = CONVERSATIONS_DIR / rel_path

    full = header + body
    full = _process_wiki_links(full, rel_path)
    fpath.write_text(full)

    _add_to_hnsw_meta(rel_path)
    for tag in tags:
        _update_concept_backlinks(tag, rel_path)

    for msg in messages or []:
        c = msg.get("content", "")
        words = re.findall(r"\b[a-zA-Z][a-zA-Z .-]{2,}\b", c)
        for w in words:
            _update_concept_backlinks(w, rel_path)

    return str(fpath)


def publish_concept(name: str, backlinks: list[str] | None = None):
    _ensure_dirs()
    slug = _slug(name)
    if not slug:
        return None
    fpath = META_DIR / f"{slug}.md"
    backlinks = backlinks or []
    if fpath.exists():
        content = fpath.read_text()
    else:
        content = (
            f"# {name}\n\n"
            f"**Created:** {time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())}\n"
            f"---\n\n"
        )
    appears = "## Appears in\n"
    if appears not in content:
        content += f"\n{appears}\n"
    for bl in backlinks:
        if f"`{bl}`" not in content:
            content += f"- `{bl}`\n"
    fpath.write_text(content)
    return str(fpath)


def publish_summary(
    name: str,
    content: str = "",
    tags: list[str] | None = None,
    example: str = "",
):
    _ensure_dirs()
    slug = _slug(name)
    if not slug:
        return None
    fpath = SUMMARIES_DIR / f"{slug}.md"
    tags = tags or []
    tag_links = " ".join(_wiki_link(t) for t in tags) if tags else ""
    if fpath.exists() and not content:
        return str(fpath)
    body = f"# {name}\n"
    if tag_links:
        body += f"\n**Tags:** {tag_links}\n"
    if content:
        body += f"\n{content}\n"
    if example:
        body += f"\n## Example\n\n{example}\n"
    fpath.write_text(body)
    return str(fpath)


def search_brain(query: str, top_k: int = 10) -> str:
    results = []
    query_lower = query.lower()

    for fpath in sorted(CONVERSATIONS_DIR.rglob("*.md")):
        rel = str(fpath.relative_to(CONVERSATIONS_DIR))
        text = fpath.read_text()
        if query_lower in text.lower():
            lines = text.splitlines()
            title_line = lines[0] if lines else ""
            snippet = ""
            for line in lines:
                if query_lower in line.lower():
                    snippet = line.strip()[:120]
                    break
            results.append(f"- `{rel}`  {title_line}  _{snippet}_")
            if len(results) >= top_k:
                break

    if not results:
        return "No results found in brain."
    return "## Brain Search Results\n\n" + "\n".join(results)
