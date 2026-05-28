# Agent System

A modular, extensible agent framework built on the OpenAI Agents SDK with persistent memory via opnbrain.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Orchestrator Agent                     │
│  plans → delegates → synthesizes → saves to brain        │
└──────────┬──────────────────────────────────────────────┘
           │ delegate_to_agent(agent_type, task)
           ▼
┌─────────────────────────────────────────────────────────┐
│                Immutable Core (base.py)                   │
│  Shared by every agent — cannot be modified              │
│                                                          │
│  • MCP: Scrapling (get, fetch, stealthy_fetch, ...)      │
│  • Tools: check_trends, validate_with_trends             │
│           brain_save_note, brain_track_concept           │
│           brain_search, brain_publish_summary            │
└─────────────────────────────────────────────────────────┘
           ▲
           │ instantiated via
┌─────────────────────────────────────────────────────────┐
│              Agent Registry (definitions/*.json)          │
│                                                          │
│  research.json    scourer.json    idea_generator.json     │
│  product_producer.json  coder.json  email_reader.json    │
│  (add new ones by creating a JSON file)                  │
└─────────────────────────────────────────────────────────┘
           │ managed via
┌─────────────────────────────────────────────────────────┐
│            Management MCP Server (optional)               │
│  list_agent_types  create_agent_type  update_agent_type  │
│  get_agent_definition  delete_agent_type  delegate       │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure

```
agent_system/
├── opnbrain.py              # Brain persistence (immutable core)
├── base.py                  # Agent factory (immutable core)
├── registry.py              # Agent definition loader/saver
├── orchestrator_agent.py    # Orchestrator agent
├── management_server.py     # MCP server for agent management
├── cli.py                   # CLI entrypoint
└── definitions/             # Agent type definitions (JSON)
    ├── research.json
    ├── scourer.json
    ├── idea_generator.json
    ├── product_producer.json
    ├── coder.json
    └── email_reader.json
```

## Immutable Core

Every agent automatically gets these capabilities. They cannot be changed through the management interface.

### MCP Server: Scrapling

| Tool | Purpose |
|------|---------|
| `get(url, ...)` | HTTP GET request — use for web searches with Google URLs |
| `fetch(url, ...)` | Playwright browser fetch for JS-heavy pages |
| `stealthy_fetch(url, ...)` | Anti-bot bypass for protected pages |
| `bulk_get(urls, ...)` | Multiple HTTP GET requests in parallel |
| `bulk_fetch(urls, ...)` | Multiple browser fetches in parallel |
| `screenshot(url, ...)` | Capture page screenshots |

### Function Tools

| Tool | Purpose |
|------|---------|
| `check_trends(keywords, timeframe, geo)` | Google Trends interest check |
| `validate_with_trends(product_idea, related_terms)` | Compare demand across terms |
| `brain_save_note(title, content, tags)` | Save a note to brain memory |
| `brain_track_concept(name)` | Register a wiki-linked concept |
| `brain_search(query)` | Search brain memory |
| `brain_publish_summary(name, content, tags)` | Create a reference summary |

## Pre-made Agent Types

| Type | Description | Key Behavior |
|------|-------------|-------------|
| **research** | Deep topic investigation | Web search + Trends + brain save |
| **scourer** | Broad data collection | Bulk fetch + structured extraction |
| **idea_generator** | Creative ideation | Brain search + synthesis + save |
| **product_producer** | Product listing creation | Brain search + generate listing |
| **coder** | Code writing/analysis | Write code + brain save |
| **email_reader** | Email summarization | Analyze + extract actions |

## CLI Usage

```bash
# List all registered agent types
./start-agent.sh

# Run a single research query
./start-agent.sh general research "trending POD niches 2026"

# Run a coder task
./start-agent.sh general coder "write a fibonacci function in python"

# Interactive mode (any agent type)
./start-agent.sh general idea_generator

# Orchestrator mode — plans and delegates
./start-agent.sh orchestrator "research POD trends, generate product ideas, and save to brain"

# Interactive orchestrator
./start-agent.sh orchestrator
```

## Creating a New Agent Type

### Method 1: Create a JSON file

Add a file to `agent_system/definitions/`:

```json
{
  "name": "my_agent",
  "description": "What this agent does",
  "instructions": "You are a specialist.\n\nYOUR JOB:\n- Describe the workflow\n- List which tools to use and when\n\nWORKFLOW:\n1. Use `brain_search()` to check prior knowledge\n2. Use `get()` to search the web\n3. Save findings with `brain_save_note()`\n4. Track concepts with `brain_track_concept()`",
  "is_premade": false
}
```

It's immediately available via:
```bash
./start-agent.sh general my_agent "your task"
```

### Method 2: Via the Management MCP Server

```bash
# Start the management server
python -m agent_system.management_server

# Connect any MCP client and call:
# create_agent_type(name="my_agent", instructions="...", description="...")
```

### Method 3: Via the Orchestrator

The orchestrator can call `create_agent_type` through the management MCP to dynamically create new agent types on the fly.

## Management MCP Server

A standalone MCP server for external tools to manage the agent registry.

**Tools:**

| Tool | Description |
|------|-------------|
| `list_agent_types` | List all registered agents |
| `get_agent_definition(name)` | Get full definition JSON |
| `create_agent_type(name, instructions, description)` | Register a new agent |
| `update_agent_type(name, instructions, description)` | Update existing |
| `delete_agent_type(name)` | Remove an agent type |
| `delegate_to_agent(agent_type, task)` | Run an agent (may timeout on long tasks) |
| `get_core_info` | List immutable core capabilities |

Run it:
```bash
python -m agent_system.management_server
```

## Orchestrator

The orchestrator agent:
1. Receives a high-level request
2. Checks brain for prior context
3. Breaks into subtasks
4. Delegates each subtask to the appropriate agent type
5. Tracks concepts in the brain
6. Synthesizes and saves final results

It uses the Python API directly (not the MCP server) so there are no timeout issues.

## opnbrain Memory

All agents persist knowledge to `~/.opnbrain/`:

| Location | Contents |
|----------|----------|
| `conversations/YYYY-MM-DD/*.md` | Notes and conversation logs |
| `.meta/*.md` | Wiki-linked concept definitions |
| `summaries/*.md` | Reference summaries |

The brain is searchable via `brain_search()` and automatically builds wiki-link cross-references between notes and concepts.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `gemma4:e2b-128k` | LLM model |
| `OPENAI_AGENTS_DISABLE_TRACING` | `1` | Disable OpenAI telemetry |
| `OPNBRAIN_DIR` | `~/.opnbrain` | Brain storage directory |

## Dependencies

- Python 3.11+
- Ollama running locally with a model (e.g., gemma4:e2b-128k)
- Scrapling CLI installed (`scrapling mcp`)
- `openai-agents` SDK
- Google Trends via `pytrends`
