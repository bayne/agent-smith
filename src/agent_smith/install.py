"""Install sub-command: diff generation, pager display, and interactive apply."""

import difflib
import json
import os
import shlex
import shutil
import subprocess
import sys


def _is_agent_smith_hook(entry: dict) -> bool:  # pyright: ignore[reportMissingTypeArgument]
    """Return True if a hook entry was created by agent-smith."""
    for hook in entry.get("hooks", []):
        if "agent-smith" in hook.get("command", ""):
            return True
    return False


def install_hooks(
    settings: dict[str, object],
    config_path: str | None = None,
    homeserver: str | None = None,
    token: str | None = None,
    room: str | None = None,
) -> dict[str, object]:
    """Merge agent-smith hooks into a settings dict, returning the result.

    Replaces any existing agent-smith hook entries rather than duplicating.
    When connection params are provided they are embedded in the hook commands
    so that environment variables are not required at runtime.
    """
    flags = ""
    if config_path:
        flags += f" -c {shlex.quote(config_path)}"
    if homeserver:
        flags += f" --homeserver {shlex.quote(homeserver)}"
    if token:
        flags += f" --token {shlex.quote(token)}"
    if room:
        flags += f" --room {shlex.quote(room)}"
    stop_entry = {
        "hooks": [
            {
                "type": "command",
                "command": f"agent-smith{flags} stop",
                "async": True,
            }
        ]
    }
    notify_entry = {
        "matcher": "permission_prompt|idle_prompt|elicitation_dialog",
        "hooks": [
            {
                "type": "command",
                "command": f"agent-smith{flags} notify",
                "async": True,
            }
        ],
    }

    settings = json.loads(json.dumps(settings))  # deep copy
    hooks: dict = settings.setdefault("hooks", {})  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType, reportMissingTypeArgument]

    # Replace existing agent-smith entries or append
    stop_list: list[dict[str, object]] = hooks.get("Stop", [])
    hooks["Stop"] = [e for e in stop_list if not _is_agent_smith_hook(e)]
    hooks["Stop"].append(stop_entry)
    notify_list: list[dict[str, object]] = hooks.get("Notification", [])
    hooks["Notification"] = [e for e in notify_list if not _is_agent_smith_hook(e)]
    hooks["Notification"].append(notify_entry)
    return settings


def generate_install_diff(path: str, original: str, updated: str) -> str:
    """Generate a unified diff between original and updated settings JSON."""
    original_lines = original.splitlines(keepends=True)
    updated_lines = updated.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines,
        updated_lines,
        fromfile=path,
        tofile=path,
    )
    return "".join(diff)


def colorize_diff(diff: str) -> str:
    """Apply ANSI colors to a unified diff string.

    - ``---``/``+++`` header lines → bold
    - ``@@`` hunk headers → cyan
    - ``-`` lines → red
    - ``+`` lines → green
    """
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"

    colored_lines: list[str] = []
    for line in diff.splitlines(keepends=True):
        if line.startswith("--- ") or line.startswith("+++ "):
            colored_lines.append(f"{BOLD}{line}{RESET}")
        elif line.startswith("@@"):
            colored_lines.append(f"{CYAN}{line}{RESET}")
        elif line.startswith("-"):
            colored_lines.append(f"{RED}{line}{RESET}")
        elif line.startswith("+"):
            colored_lines.append(f"{GREEN}{line}{RESET}")
        else:
            colored_lines.append(line)
    return "".join(colored_lines)


def _get_pager_cmd() -> list[str] | None:
    """Return the pager command as an argv list, or None if unavailable."""
    pager_env = os.environ.get("PAGER")
    if pager_env:
        return shlex.split(pager_env)
    if shutil.which("less"):
        return ["less", "-R"]
    if shutil.which("more"):
        return ["more"]
    return None


def show_in_pager(text: str) -> None:
    """Display *text* in the user's default pager.

    Falls back to printing directly when no pager is available or the pager
    exits with an error.
    """
    pager_cmd = _get_pager_cmd()
    if pager_cmd is None:
        print(text, end="")
        return
    try:
        _ = subprocess.run(pager_cmd, input=text.encode(), check=False)
    except FileNotFoundError:
        print(text, end="")


def confirm_apply() -> bool:
    """Prompt the user to accept or reject changes. Returns True for yes."""
    try:
        answer = input("Apply these changes? [y/N] ")
        return answer.strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def run_install(
    settings_path: str,
    config_path: str | None = None,
    homeserver: str | None = None,
    token: str | None = None,
    room: str | None = None,
) -> None:
    """Run the install sub-command end-to-end.

    In interactive mode (stdout is a TTY) the coloured diff is displayed in the
    user's pager, then the user is prompted to apply.  In non-interactive mode
    the raw diff is printed to stdout for scripting.
    """
    if os.path.exists(settings_path):
        with open(settings_path) as f:
            settings = json.load(f)
    else:
        settings = {}

    original_text = json.dumps(settings, indent=2) + "\n"

    updated = install_hooks(
        settings,
        config_path=config_path,
        homeserver=homeserver,
        token=token,
        room=room,
    )
    updated_text = json.dumps(updated, indent=2) + "\n"

    diff = generate_install_diff(settings_path, original_text, updated_text)
    if not diff:
        print("No changes needed.")
        return

    interactive = sys.stdin.isatty() and sys.stdout.isatty()

    if not interactive:
        print(diff, end="")
        return

    show_in_pager(colorize_diff(diff))

    if confirm_apply():
        with open(settings_path, "w") as f:
            _ = f.write(updated_text)
        print(f"Changes written to {settings_path}")
    else:
        print("No changes applied.")
