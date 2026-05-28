#!/usr/bin/env bash
set -eu

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$REPO_DIR/mcp_server/venv/bin/python"

export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:e2b-128k}"
export OPENAI_AGENTS_DISABLE_TRACING=1
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$REPO_DIR"

MODE="${1:-general}"
shift 2>/dev/null || true

if [ "$MODE" = "general" ] || [ "$MODE" = "g" ]; then
    echo " General Agent  (Scrapling + Trends + opnbrain)"
elif [ "$MODE" = "orchestrator" ] || [ "$MODE" = "o" ]; then
    echo " Orchestrator Agent  (delegates + opnbrain)"
fi
echo "   Ollama: $OLLAMA_URL  Model: $OLLAMA_MODEL"
echo "   Usage: start-agent.sh [general|orchestrator] [query...]"
echo "         (no query = interactive mode)"
echo ""

exec "$VENV_PYTHON" -u -m agent_system.cli "$MODE" "$@"
