#!/usr/bin/env bash
set -eu
# pipefail not set to avoid issues with PYTHONPATH being unbound

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$REPO_DIR/mcp_server/venv/bin/python"

export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:e2b-128k}"
export OPENAI_AGENTS_DISABLE_TRACING=1
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$REPO_DIR"

echo "🔍 Research Agent CLI"
echo "   Ollama: $OLLAMA_URL  Model: $OLLAMA_MODEL"
echo "   Usage:  start-research.sh [topic]"
echo "           (no args = interactive mode)"
echo ""

exec "$VENV_PYTHON" -m research_agent.cli "$@"
