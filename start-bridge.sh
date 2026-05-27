#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "Starting Ollama MCP Bridge on http://localhost:8000"
echo "Servers: scrapling + pod-market"
echo "Model: gemma4:e2b-128k"
echo ""

exec ollama-mcp-bridge \
  --config mcp-bridge-config.json \
  --host 0.0.0.0 \
  --port 8000 \
  --max-tool-rounds 10 \
  --ollama-url http://localhost:11434
