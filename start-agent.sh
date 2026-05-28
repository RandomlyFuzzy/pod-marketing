#!/usr/bin/env bash
set -eu

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$REPO_DIR/mcp_server/venv/bin/python"

export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:e2b-128k}"
export OPENAI_AGENTS_DISABLE_TRACING=1
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$REPO_DIR"

echo " Agent System"
echo "   Ollama: $OLLAMA_URL  Model: $OLLAMA_MODEL"
echo "   Usage:"
echo "     start-agent.sh                       — list agents"
echo "     start-agent.sh general <type>        — interactive [type]"
echo "     start-agent.sh general <type> <q>    — single-shot [type]"
echo "     start-agent.sh orchestrator [query]  — orchestrator mode"
echo "     start-agent.sh planner [goal]        — planner agent"
echo "     start-agent.sh reviewer [task]       — reviewer agent"
echo ""

exec "$VENV_PYTHON" -u -m agent_system.cli "$@"
