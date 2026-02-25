#!/usr/bin/env bash
# Manual test script for agent-smith MCP server.
#
# Requires MATRIX_* env vars to be set for the send test.
# Uses fastmcp dev for interactive testing.

set -euo pipefail

echo "=== agent-smith MCP server manual tests ==="
echo ""
echo "MATRIX_HOMESERVER:   ${MATRIX_HOMESERVER:-(not set)}"
echo "MATRIX_ROOM_ID:      ${MATRIX_ROOM_ID:-(not set)}"
echo "MATRIX_ACCESS_TOKEN: ${MATRIX_ACCESS_TOKEN:+(set)}"
echo ""

echo "--- Option 1: Add to Claude Code ---"
echo "  claude mcp add agent-smith -- uv run --directory $(pwd) agent-smith"
echo ""

echo "--- Option 2: Interactive dev mode ---"
echo "  uv run fastmcp dev inspector src/agent_smith/main.py:mcp"
echo ""

echo "--- Option 3: Run directly on stdio ---"
echo "  uv run agent-smith"
echo ""
