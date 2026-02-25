# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

agent-smith is an MCP server that gives Claude Code the ability to send messages to a Matrix chat room. It uses FastMCP to expose a `send_message` tool and `matrix-nio` to communicate with Matrix.

Managed with [uv](https://docs.astral.sh/uv/). Requires Python >= 3.14.

## Commands

- **Install dependencies:** `uv sync`
- **Run MCP server:** `uv run agent-smith`
- **Send message directly:** `uv run agent-smith send "your message here"`
- **Run tests:** `uv run pytest`
- **Add a dependency:** `uv add <package>`
- **Add to Claude Code:** `claude mcp add agent-smith -- uv run --directory /path/to/agent-smith agent-smith`

## Configuration

Set these environment variables:

- `MATRIX_HOMESERVER` — Matrix server URL
- `MATRIX_ACCESS_TOKEN` — Matrix access token
- `MATRIX_ROOM_ID` — Target Matrix room ID

## Hooks

Built-in subcommands integrate with Claude Code's hook system to send Matrix notifications:

- `agent-smith stop` — reads Stop hook JSON from stdin, formats and sends a notification
- `agent-smith notify` — reads Notification hook JSON from stdin, formats and sends a notification
- `hooks/settings.example.json` — example `~/.claude/settings.json` config

Set `AGENT_SMITH_DIR` in the settings env block to this repo's path.

## Architecture

Single module at `src/agent_smith/main.py`. A `FastMCP` server instance exposes the `send_message` tool, which accepts a message string and sends it to the configured Matrix room via `matrix-nio` `AsyncClient`. The CLI uses subcommands: `send` for direct messages, `stop` and `notify` for hook integration. With no subcommand it starts the MCP server. Entry point is `main()`, registered as the `agent-smith` console script.
