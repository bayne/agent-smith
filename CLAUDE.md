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

Place a dotenv-format file at `~/.config/agent-smith/config.env` — it is loaded automatically:

```env
MATRIX_HOMESERVER=https://matrix.example.org
MATRIX_ACCESS_TOKEN=syt_...
MATRIX_ROOM_ID=!abc:example.org
```

Alternatively, set these environment variables directly (they take precedence over the config file):

- `MATRIX_HOMESERVER` — Matrix server URL
- `MATRIX_ACCESS_TOKEN` — Matrix access token
- `MATRIX_ROOM_ID` — Target Matrix room ID

## Hooks

Built-in subcommands integrate with Claude Code's hook system to send Matrix notifications:

- `agent-smith stop` — reads Stop hook JSON from stdin, formats and sends a notification
- `agent-smith notify` — reads Notification hook JSON from stdin, formats and sends a notification
- `agent-smith install <settings.json>` — shows a coloured diff of hook changes, prompts to apply
- `hooks/settings.example.json` — example `~/.claude/settings.json` config

Use `install` to add hooks to your settings file:

```sh
agent-smith install ~/.claude/settings.json                         # interactive: review diff in pager, then accept/reject
agent-smith install -c /path/to/config.env ~/.claude/settings.json  # embed a config file path in hook commands
agent-smith install ~/.claude/settings.json > changes.diff          # non-interactive: raw diff to stdout
```

## Architecture

- `src/agent_smith/main.py` — CLI entry point and MCP server. A `FastMCP` server instance exposes the `send_message` tool, which accepts a message string and sends it to the configured Matrix room via `matrix-nio` `AsyncClient`. The CLI uses subcommands: `send` for direct messages, `stop` and `notify` for hook integration, `install` for interactive hook installation. With no subcommand it starts the MCP server. Entry point is `main()`, registered as the `agent-smith` console script.
- `src/agent_smith/install.py` — Install sub-command logic: hook merging (`install_hooks`), unified diff generation (`generate_install_diff`), ANSI colorization (`colorize_diff`), pager display (`show_in_pager`), interactive confirmation (`confirm_apply`), and end-to-end orchestration (`run_install`).
