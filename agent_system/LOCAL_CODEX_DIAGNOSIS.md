# Local Codex-Style Agent System Diagnosis

## What this project currently is

This repo is a local multi-agent wrapper around:

- Ollama-compatible chat models exposed through `http://localhost:11434/v1`
- the OpenAI Agents SDK
- JSON agent definitions in `agent_system/definitions/`
- optional MCP tools, currently mainly Scrapling
- persistent memory through `opnbrain`
- a planner/reviewer/orchestrator loop

The intended shape is close to a local Codex-style system: a front agent receives a goal, chooses specialist agents, calls tools, stores intermediate results, reviews the output, and repeats if quality is not good enough.

## Why the current setup did not work

### 1. The planner was not grounded in the real team manifest

The planner instructions mentioned some tools and agents, but there was no single source of truth injected into the planner that listed every registered agent, its model, its function tools, and its MCP tools.

Effect:

- the planner invented agent names like `research_and_analysis` or `enhancer`
- it guessed which team could do web work
- it wrote plans instead of making valid tool calls

Fix:

- `registry.team_manifest()` now builds the live team/tool manifest from the JSON registry
- planner instructions now include that manifest
- `list_agent_types()` now returns models, function tools, MCP servers, and MCP tools
- `base.py` injects the same manifest when a planner is built from `planner.json`

### 2. There were two planner paths

There is a hardcoded planner in `planner_agent.py` and a registry-defined planner in `definitions/planner.json`.

Effect:

- older CLI paths could run planner/reviewer/specialists directly
- direct runs bypassed the orchestrator quality loop and used different prompts/tool setup
- these did not have identical prompts or tool visibility

Fix:

- the public CLI now routes all non-`list` execution through `run_orchestrator()`
- legacy shapes like `./start-agent.sh general researcher "..."` are accepted only as compatibility syntax and become orchestrator goals
- planner and reviewer remain internal modules used by the orchestrator

### 3. The reviewer verdict parser was brittle

The local model often emits reasoning text before the verdict, such as:

`...final output.**SEVERITY: MISSING**`

The parser only accepted lines that started with `**SEVERITY:`, so it missed valid verdicts.

Effect:

- valid reviewer verdicts were treated as missing
- the orchestrator took the wrong recovery path
- runs spiraled through repeated iterations

Fix:

- `_parse_severity()` now uses a regex and accepts the marker anywhere in the reviewer output
- `**SEVERITY: NONE**` is treated as success for compatibility with `reviewer.json`

### 4. The orchestrator could run essentially forever

`run_orchestrator()` defaulted to `max_iterations=5000000`.

Effect:

- a bad planner/reviewer loop looked like a crash or hang
- failed runs produced huge output directories

Fix:

- default max iterations is now `5`

### 5. Local models may not actually support reliable tool calling

The OpenAI Agents SDK can expose tools, but the selected Ollama model still has to emit tool calls in the expected OpenAI-compatible format.

In saved outputs, the planner repeatedly described what it would do instead of calling tools. That is not a Python crash; it is a model/tool-calling capability gap.

What is missing for a real local Codex equivalent:

- a model that reliably supports OpenAI-style tool calls through Ollama
- a small deterministic controller that verifies tool calls happened when a task requires execution
- sandboxed filesystem tools for reading, editing, testing, and patching code
- explicit approval gates for destructive or external actions
- task-state tracking outside the model text
- robust run logs that separate model reasoning, tool calls, tool output, and final answer

### 6. External/current-data work depends on Scrapling MCP actually initializing

Many agents assume Scrapling tools exist. If `scrapling mcp` is missing, not on `PATH`, cannot initialize as an MCP stdio server, or cannot access the network, researcher-style agents cannot gather live data.

Observed in this workspace:

- `scrapling` exists at `/home/rf/.local/bin/scrapling`
- the project venv does not have the `scrapling` Python package installed
- `/home/rf/.local/bin/scrapling` runs under `/usr/bin/python3`, not the project venv
- direct SDK initialization of `scrapling mcp` timed out waiting for the MCP `initialize` response, even with a 30 second timeout

Check:

```bash
which scrapling
mcp_server/venv/bin/python -m pip show scrapling
scrapling mcp
```

## Team and tool source of truth

The registry now exposes this through:

```bash
./start-agent.sh list
```

Each entry shows:

- agent name
- description
- model
- function tools
- MCP tools

The planner sees the same manifest in its system instructions.

## Recommended architecture to make this more like Codex

1. Keep the JSON registry as the declarative team catalog.
2. Keep model/tool selection deterministic in Python, not hidden only in prompts.
3. Add a controller-level check: if a task requires execution and zero tool calls occurred, fail fast and retry with a stricter prompt or a different model.
4. Add first-class local code tools:
   - list files
   - read file
   - search text
   - apply patch
   - run command
   - run tests
5. Separate planner responsibilities:
   - planner decides steps and target agents
   - executor performs tool calls
   - reviewer checks outputs
6. Use a tool-capable model for the planner. If the local planner model cannot call tools reliably, use it for text planning only and let Python execute the plan.
7. Keep max iteration limits low. Infinite self-correction loops are a failure mode, not autonomy.

## Useful smoke checks

```bash
mcp_server/venv/bin/python -m compileall agent_system pipeline research_agent mcp_server
./start-agent.sh list
timeout 30 ./start-agent.sh orchestrator "Say ping and stop."
timeout 30 ./start-agent.sh general researcher "Name two Scrapling tools available to the researcher."
```

If the planner only explains what it would do and never calls tools, the active model is not functioning as a tool-calling planner.
