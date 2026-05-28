#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Use the existing venv if available
PYTHON="python3"
if [ -f "mcp_server/venv/bin/python" ]; then
    PYTHON="mcp_server/venv/bin/python"
fi

# Ensure dependencies
$PYTHON -m pip install -q fastapi uvicorn jinja2 httpx python-dotenv 2>/dev/null || true

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║        POD Pipeline — Research to Publish       ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Phase 1: 🔍 Research                           ║"
echo "║  Phase 2: ✅ Validate                           ║"
echo "║  Phase 3: 🎨 Create                             ║"
echo "║  Phase 4: 🚀 Publish                            ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Powered by Ollama + Scrapling + Printify       ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

PORT="${PIPELINE_PORT:-8001}"
echo "Starting on http://localhost:$PORT"
echo ""

# Source .env if it exists
if [ -f "mcp_server/.env" ]; then
    set -a
    source mcp_server/.env
    set +a
fi

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}" \
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:e2b-128k}" \
PIPELINE_PORT="$PORT" \
exec "$PYTHON" -m pipeline.main
