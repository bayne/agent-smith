# agent-smith

An MCP server that gives [Claude Code](https://claude.ai/code) the ability to send messages to a [Matrix](https://matrix.org/) chat room.

Claude Code can call the `send_message` tool to post messages to your Matrix room on demand — useful for notifications, status updates, or anything else you want relayed to chat.

## Setup

Requires Python >= 3.14 and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install .
```

### Configuration

create an env file:

```bash
MATRIX_HOMESERVER="https://matrix.example.org"
MATRIX_ACCESS_TOKEN="syt_your_token_here"
MATRIX_ROOM_ID="!your_room_id:example.org"
```

You can generate an access token from Element (Settings > Help & About > Access Token) or via the Matrix client-server API.

### Add to Claude Code



## CLI

| Command | Description |
|---|---|
| `agent-smith` | Start the MCP server |
| `agent-smith send "msg"` | Send a message directly |
| `agent-smith stop` | Read Stop hook JSON from stdin, format and send notification |
| `agent-smith notify` | Read Notification hook JSON from stdin, format and send notification |

## MCP Tool

| Tool | Parameters | Description |
|---|---|---|
| `send_message` | `message: str` | Send a message to the configured Matrix room |
