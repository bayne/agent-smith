"""agent-smith: MCP server that sends messages to Matrix chat."""

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from nio import AsyncClient, RoomSendResponse

from agent_smith.install import run_install

log = logging.getLogger("agent-smith")

mcp = FastMCP("agent-smith")


def get_config(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Load configuration from CLI overrides then environment variables."""
    overrides = overrides or {}
    required = {
        "MATRIX_HOMESERVER": "Matrix homeserver URL (e.g. https://matrix.example.org)",
        "MATRIX_ACCESS_TOKEN": "Matrix access token",
        "MATRIX_ROOM_ID": "Matrix room ID (e.g. !abc:example.org)",
    }
    config = {}
    missing = []
    for var, description in required.items():
        value = overrides.get(var) or os.environ.get(var)
        if not value:
            missing.append(f"  {var} - {description}")
        else:
            config[var] = value
    if missing:
        raise ValueError(
            "Missing required environment variables:\n" + "\n".join(missing)
        )
    log.debug("Configuration loaded successfully")
    return config


async def send_matrix_message(config: dict[str, str], body: str) -> None:
    """Send a plain text message to the configured Matrix room."""
    client = AsyncClient(config["MATRIX_HOMESERVER"])
    client.access_token = config["MATRIX_ACCESS_TOKEN"]
    client.user_id = os.environ.get("MATRIX_USER_ID", "@agent-smith:matrix")
    content = {
        "msgtype": "m.text",
        "body": body,
    }
    log.info(
        "Request: room_send(room_id=%s, message_type=%s, content=%s)",
        config["MATRIX_ROOM_ID"],
        "m.room.message",
        json.dumps(content),
    )
    try:
        response = await client.room_send(
            room_id=config["MATRIX_ROOM_ID"],
            message_type="m.room.message",
            content=content,
        )
        if not isinstance(response, RoomSendResponse):
            raise RuntimeError(f"Matrix send failed: {response}")
        log.info(
            "Response: event_id=%s, room_id=%s", response.event_id, response.room_id
        )
    finally:
        await client.close()


@mcp.tool
async def send_message(message: str) -> str:
    """Send a message to the configured Matrix room."""
    config = get_config()
    await send_matrix_message(config, message)
    return "Message sent"


def load_config_file(path: str) -> dict[str, str]:
    """Load MATRIX_* variables from a dotenv-style config file."""
    from dotenv import dotenv_values

    values = dotenv_values(path)
    return {k: v for k, v in values.items() if k.startswith("MATRIX_") and v}


def _truncate(text: str, limit: int = 500) -> str:
    """Truncate text to *limit* characters, adding an ellipsis if shortened."""
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def format_stop_message(data: dict) -> str | None:  # pyright: ignore[reportMissingTypeArgument]
    """Format a Stop hook JSON payload into a Matrix message.

    Returns None if stop_hook_active is true (to avoid notification loops).
    """
    if data.get("stop_hook_active") is True:
        return None
    cwd = data.get("cwd", "unknown")
    project = os.path.basename(cwd)
    last_message = data.get("last_assistant_message", "")

    if last_message:
        return f"Task complete in **{project}**:\n\n{_truncate(last_message)}"
    return f"Task complete in **{project}**"


def format_notify_message(data: dict) -> str:  # pyright: ignore[reportMissingTypeArgument]
    """Format a Notification hook JSON payload into a Matrix message."""
    notification_type = data.get("notification_type", "unknown")
    message = data.get("message", "Input needed")
    title = data.get("title")
    cwd = data.get("cwd", "unknown")
    project = os.path.basename(cwd)

    labels = {
        "permission_prompt": "Permission needed",
        "idle_prompt": "Waiting for input",
        "elicitation_dialog": "Question for you",
    }
    label = labels.get(notification_type, "Notification")

    if title:
        return f"{label} in **{project}** — {title}: {message}"
    return f"{label} in **{project}**: {message}"


def read_stdin_json() -> dict[str, Any]:
    """Read JSON from stdin and return as a dict."""
    raw = sys.stdin.read()
    return json.loads(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agent-smith",
        description="MCP server that gives Claude Code the ability to send messages to a Matrix chat room.",
        epilog="""\
examples:
  agent-smith                         start the MCP server (stdio transport)
  agent-smith send "hello world"      send a message directly
  agent-smith -c .env send "hello"    send using a config file
  agent-smith stop                    handle a Stop hook (reads JSON from stdin)
  agent-smith notify                  handle a Notification hook (reads JSON from stdin)
  agent-smith install settings.json              show diff of hook changes for a settings file
  agent-smith install -c config.env settings.json  show diff with a config file path in hook commands

environment variables:
  MATRIX_HOMESERVER    Matrix server URL (e.g. https://matrix.example.org)
  MATRIX_ACCESS_TOKEN  Matrix access token
  MATRIX_ROOM_ID       Target room ID (e.g. !abc:example.org)
  LOG_LEVEL            Logging level (default: WARNING)
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        "-c",
        metavar="FILE",
        help="path to config file (dotenv format with MATRIX_* variables)",
    )
    parser.add_argument("--homeserver", metavar="URL", help="Matrix homeserver URL")
    parser.add_argument("--token", metavar="TOKEN", help="Matrix access token")
    parser.add_argument("--room", metavar="ROOM_ID", help="Matrix room ID")

    subparsers = parser.add_subparsers(dest="command")

    send_parser = subparsers.add_parser("send", help="send a message directly")
    send_parser.add_argument("message", nargs="+", help="message text")

    subparsers.add_parser(
        "stop", help="read Stop hook JSON from stdin and send notification"
    )
    subparsers.add_parser(
        "notify", help="read Notification hook JSON from stdin and send notification"
    )

    install_parser = subparsers.add_parser(
        "install",
        help="show a diff of agent-smith hooks for a Claude Code settings.json",
    )
    install_parser.add_argument(
        "--config",
        "-c",
        metavar="FILE",
        dest="install_config",
        help="path to config file to embed in hook commands",
    )
    install_parser.add_argument(
        "settings_file",
        help="path to settings.json to update",
    )

    return parser.parse_args()


def _build_overrides(args: argparse.Namespace) -> dict[str, str]:
    """Build config overrides from parsed CLI arguments."""
    overrides: dict[str, str] = {}
    if args.config:
        overrides.update(load_config_file(args.config))
    if args.homeserver:
        overrides["MATRIX_HOMESERVER"] = args.homeserver
    if args.token:
        overrides["MATRIX_ACCESS_TOKEN"] = args.token
    if args.room:
        overrides["MATRIX_ROOM_ID"] = args.room
    return overrides


def main() -> None:
    """Entry point: route to MCP server or subcommand."""
    load_dotenv()
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=os.environ.get("LOG_LEVEL", "WARNING").upper(),
    )
    args = parse_args()

    if args.command == "send":
        message = " ".join(args.message)
        config = get_config(_build_overrides(args))
        asyncio.run(send_matrix_message(config, message))
        print("Message sent")
    elif args.command == "stop":
        data = read_stdin_json()
        message = format_stop_message(data)
        if message is None:
            return
        config = get_config(_build_overrides(args))
        asyncio.run(send_matrix_message(config, message))
        print("Message sent")
    elif args.command == "notify":
        data = read_stdin_json()
        message = format_notify_message(data)
        config = get_config(_build_overrides(args))
        asyncio.run(send_matrix_message(config, message))
        print("Message sent")
    elif args.command == "install":
        config_path = getattr(args, "install_config", None) or args.config
        overrides = _build_overrides(args)
        run_install(
            args.settings_file,
            config_path=config_path,
            homeserver=overrides.get("MATRIX_HOMESERVER"),
            token=overrides.get("MATRIX_ACCESS_TOKEN"),
            room=overrides.get("MATRIX_ROOM_ID"),
        )
    else:
        mcp.run()


if __name__ == "__main__":
    main()
