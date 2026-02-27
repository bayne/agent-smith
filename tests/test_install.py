"""Tests for agent_smith.install."""

import json
from unittest.mock import patch

import pytest

from agent_smith.install import (
    _get_pager_cmd,
    colorize_diff,
    confirm_apply,
    generate_install_diff,
    install_hooks,
    run_install,
    show_in_pager,
)


class TestInstallHooks:
    def test_into_empty_settings(self):
        result = install_hooks({})
        assert "Stop" in result["hooks"]
        assert "Notification" in result["hooks"]
        assert len(result["hooks"]["Stop"]) == 1
        assert len(result["hooks"]["Notification"]) == 1
        # Commands should not have -c flag
        stop_cmd = result["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert stop_cmd == "agent-smith stop"

    def test_with_config_path(self):
        result = install_hooks({}, config_path="/etc/agent-smith.env")
        stop_cmd = result["hooks"]["Stop"][0]["hooks"][0]["command"]
        notify_cmd = result["hooks"]["Notification"][0]["hooks"][0]["command"]
        assert stop_cmd == "agent-smith -c /etc/agent-smith.env stop"
        assert notify_cmd == "agent-smith -c /etc/agent-smith.env notify"

    def test_preserves_existing_non_agent_smith_hooks(self):
        settings = {
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}],
            }
        }
        result = install_hooks(settings)
        # Original hook preserved, agent-smith hook appended
        assert len(result["hooks"]["Stop"]) == 2
        assert result["hooks"]["Stop"][0]["hooks"][0]["command"] == "echo done"

    def test_replaces_existing_agent_smith_hooks(self):
        settings = {
            "hooks": {
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "agent-smith -c old.env stop",
                            }
                        ]
                    }
                ],
            }
        }
        result = install_hooks(settings, config_path="/new.env")
        # Old agent-smith entry replaced, not duplicated
        assert len(result["hooks"]["Stop"]) == 1
        assert "/new.env" in result["hooks"]["Stop"][0]["hooks"][0]["command"]

    def test_preserves_other_settings_keys(self):
        settings = {"permissions": {"allow": ["Read"]}, "hooks": {}}
        result = install_hooks(settings)
        assert result["permissions"] == {"allow": ["Read"]}

    def test_does_not_mutate_input(self):
        settings = {"hooks": {"Stop": []}}
        install_hooks(settings)
        assert settings["hooks"]["Stop"] == []

    def test_notify_entry_has_matcher(self):
        result = install_hooks({})
        entry = result["hooks"]["Notification"][0]
        assert "matcher" in entry

    def test_hooks_are_async(self):
        result = install_hooks({})
        stop_hook = result["hooks"]["Stop"][0]["hooks"][0]
        notify_hook = result["hooks"]["Notification"][0]["hooks"][0]
        assert stop_hook["async"] is True
        assert notify_hook["async"] is True

    def test_with_connection_params(self):
        result = install_hooks(
            {},
            homeserver="https://matrix.example.org",
            token="syt_test_token",
            room="!abc:example.org",
        )
        stop_cmd = result["hooks"]["Stop"][0]["hooks"][0]["command"]
        notify_cmd = result["hooks"]["Notification"][0]["hooks"][0]["command"]
        assert "--homeserver https://matrix.example.org" in stop_cmd
        assert "--token syt_test_token" in stop_cmd
        assert "--room '!abc:example.org'" in stop_cmd
        assert stop_cmd.endswith(" stop")
        assert notify_cmd.endswith(" notify")

    def test_with_config_and_connection_params(self):
        result = install_hooks(
            {},
            config_path="/etc/agent-smith.env",
            homeserver="https://matrix.example.org",
        )
        stop_cmd = result["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert "-c /etc/agent-smith.env" in stop_cmd
        assert "--homeserver https://matrix.example.org" in stop_cmd

    def test_partial_connection_params(self):
        result = install_hooks({}, homeserver="https://matrix.example.org")
        stop_cmd = result["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert "--homeserver https://matrix.example.org" in stop_cmd
        assert "--token" not in stop_cmd
        assert "--room" not in stop_cmd


class TestGenerateInstallDiff:
    def test_returns_empty_when_no_changes(self):
        text = '{\n  "hooks": {}\n}\n'
        assert generate_install_diff("settings.json", text, text) == ""

    def test_returns_unified_diff_for_changes(self):
        original = '{\n  "hooks": {}\n}\n'
        updated = '{\n  "hooks": {\n    "Stop": []\n  }\n}\n'
        diff = generate_install_diff("settings.json", original, updated)
        assert diff.startswith("--- settings.json")
        assert "+++ settings.json" in diff
        assert '-  "hooks": {}' in diff
        assert '+    "Stop": []' in diff

    def test_new_file_shows_all_additions(self):
        original = "{}\n"
        updated = '{\n  "hooks": {\n    "Stop": []\n  }\n}\n'
        diff = generate_install_diff("settings.json", original, updated)
        assert "-{}" in diff
        assert '+  "hooks"' in diff

    def test_uses_path_in_header(self):
        original = "{}\n"
        updated = '{\n  "key": 1\n}\n'
        diff = generate_install_diff(
            "/home/user/.claude/settings.json", original, updated
        )
        assert "--- /home/user/.claude/settings.json" in diff
        assert "+++ /home/user/.claude/settings.json" in diff

    def test_end_to_end_with_install_hooks(self):
        settings: dict = {}
        original = json.dumps(settings, indent=2) + "\n"
        updated_settings = install_hooks(settings)
        updated = json.dumps(updated_settings, indent=2) + "\n"
        diff = generate_install_diff("settings.json", original, updated)
        assert "agent-smith" in diff
        assert "++" in diff


class TestColorizeDiff:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"

    def test_header_lines_are_bold(self):
        diff = "--- a.json\n+++ b.json\n@@ -1 +1 @@\n-old\n+new\n"
        result = colorize_diff(diff)
        assert result.startswith(f"{self.BOLD}--- a.json\n{self.RESET}")
        assert f"{self.BOLD}+++ b.json\n{self.RESET}" in result

    def test_removed_lines_are_red(self):
        diff = "--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n"
        result = colorize_diff(diff)
        assert f"{self.RED}-old\n{self.RESET}" in result

    def test_added_lines_are_green(self):
        diff = "--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n"
        result = colorize_diff(diff)
        assert f"{self.GREEN}+new\n{self.RESET}" in result

    def test_hunk_headers_are_cyan(self):
        diff = "--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n"
        result = colorize_diff(diff)
        assert f"{self.CYAN}@@ -1 +1 @@\n{self.RESET}" in result

    def test_context_lines_are_plain(self):
        diff = "--- a\n+++ b\n@@ -1,3 +1,3 @@\n context\n-old\n+new\n"
        result = colorize_diff(diff)
        assert " context\n" in result
        # context line should not have its own color applied
        COLOR_PREFIXES = (self.RED, self.GREEN, self.CYAN, self.BOLD)
        for line in result.splitlines(keepends=True):
            stripped = line.lstrip(self.RESET)
            if stripped.startswith(" context"):
                assert not any(stripped.startswith(c) for c in COLOR_PREFIXES)
                break

    def test_empty_string(self):
        assert colorize_diff("") == ""


class TestGetPagerCmd:
    def test_uses_pager_env_var(self, monkeypatch):
        monkeypatch.setenv("PAGER", "bat --style=plain")
        result = _get_pager_cmd()
        assert result == ["bat", "--style=plain"]

    def test_falls_back_to_less(self, monkeypatch):
        monkeypatch.delenv("PAGER", raising=False)
        with patch("agent_smith.install.shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: (
                "/usr/bin/less" if cmd == "less" else None
            )
            result = _get_pager_cmd()
        assert result == ["less", "-R"]

    def test_falls_back_to_more(self, monkeypatch):
        monkeypatch.delenv("PAGER", raising=False)
        with patch("agent_smith.install.shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: (
                "/usr/bin/more" if cmd == "more" else None
            )
            result = _get_pager_cmd()
        assert result == ["more"]

    def test_returns_none_when_no_pager(self, monkeypatch):
        monkeypatch.delenv("PAGER", raising=False)
        with patch("agent_smith.install.shutil.which", return_value=None):
            result = _get_pager_cmd()
        assert result is None


class TestShowInPager:
    def test_sends_text_to_pager(self):
        with patch("agent_smith.install._get_pager_cmd", return_value=["less", "-R"]):
            with patch("agent_smith.install.subprocess.run") as mock_run:
                show_in_pager("hello diff")
                mock_run.assert_called_once_with(
                    ["less", "-R"], input=b"hello diff", check=False
                )

    def test_prints_when_no_pager(self, capsys):
        with patch("agent_smith.install._get_pager_cmd", return_value=None):
            show_in_pager("hello diff")
        assert capsys.readouterr().out == "hello diff"

    def test_prints_on_file_not_found(self, capsys):
        with patch("agent_smith.install._get_pager_cmd", return_value=["nonexistent"]):
            with patch(
                "agent_smith.install.subprocess.run",
                side_effect=FileNotFoundError,
            ):
                show_in_pager("hello diff")
        assert capsys.readouterr().out == "hello diff"


class TestConfirmApply:
    def test_accepts_y(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert confirm_apply() is True

    def test_accepts_yes(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "yes")
        assert confirm_apply() is True

    def test_accepts_YES_case_insensitive(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "YES")
        assert confirm_apply() is True

    def test_rejects_n(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert confirm_apply() is False

    def test_rejects_empty(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert confirm_apply() is False

    def test_rejects_arbitrary_text(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "sure")
        assert confirm_apply() is False

    def test_eof_returns_false(self, monkeypatch):
        def raise_eof(_):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        assert confirm_apply() is False

    def test_keyboard_interrupt_returns_false(self, monkeypatch):
        def raise_interrupt(_):
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", raise_interrupt)
        assert confirm_apply() is False


class TestRunInstall:
    def test_no_changes_needed(self, tmp_path, capsys):
        """When hooks are already installed, prints no-changes message."""
        settings = install_hooks({})
        path = tmp_path / "settings.json"
        path.write_text(json.dumps(settings, indent=2) + "\n")

        run_install(str(path))

        assert "No changes needed." in capsys.readouterr().out

    def test_non_interactive_prints_raw_diff(self, tmp_path):
        """When not a TTY, prints the raw diff without color."""
        path = tmp_path / "settings.json"
        path.write_text("{}\n")

        with (
            patch("agent_smith.install.sys.stdin") as mock_stdin,
            patch("agent_smith.install.sys.stdout") as mock_stdout,
            patch("builtins.print") as mock_print,
        ):
            mock_stdin.isatty.return_value = False
            mock_stdout.isatty.return_value = False

            run_install(str(path))

        # Should have printed the diff (first call) without ANSI codes
        printed = mock_print.call_args_list[0][0][0]
        assert "---" in printed
        assert "\033[" not in printed

    def test_interactive_shows_pager_and_applies(self, tmp_path, capsys):
        """In interactive mode, shows pager then writes on confirmation."""
        path = tmp_path / "settings.json"
        path.write_text("{}\n")

        with (
            patch("agent_smith.install.sys.stdin") as mock_stdin,
            patch("agent_smith.install.sys.stdout") as mock_stdout,
            patch("agent_smith.install.show_in_pager") as mock_pager,
            patch("agent_smith.install.confirm_apply", return_value=True),
        ):
            mock_stdin.isatty.return_value = True
            mock_stdout.isatty.return_value = True

            run_install(str(path))

        # Pager was called with colorized diff
        mock_pager.assert_called_once()
        pager_text = mock_pager.call_args[0][0]
        assert "\033[" in pager_text  # contains ANSI codes

        # File was updated
        result = json.loads(path.read_text())
        assert "hooks" in result
        assert "Stop" in result["hooks"]

    def test_interactive_rejects_leaves_file_unchanged(self, tmp_path, capsys):
        """In interactive mode, declining leaves the file as-is."""
        path = tmp_path / "settings.json"
        original_content = "{}\n"
        path.write_text(original_content)

        with (
            patch("agent_smith.install.sys.stdin") as mock_stdin,
            patch("agent_smith.install.sys.stdout") as mock_stdout,
            patch("agent_smith.install.show_in_pager"),
            patch("agent_smith.install.confirm_apply", return_value=False),
        ):
            mock_stdin.isatty.return_value = True
            mock_stdout.isatty.return_value = True

            run_install(str(path))

        # File unchanged
        assert path.read_text() == original_content

    def test_new_file_created_on_apply(self, tmp_path, capsys):
        """When the settings file doesn't exist, creates it on apply."""
        path = tmp_path / "new-settings.json"
        assert not path.exists()

        with (
            patch("agent_smith.install.sys.stdin") as mock_stdin,
            patch("agent_smith.install.sys.stdout") as mock_stdout,
            patch("agent_smith.install.show_in_pager"),
            patch("agent_smith.install.confirm_apply", return_value=True),
        ):
            mock_stdin.isatty.return_value = True
            mock_stdout.isatty.return_value = True

            run_install(str(path))

        assert path.exists()
        result = json.loads(path.read_text())
        assert "hooks" in result

    def test_passes_config_options_through(self, tmp_path):
        """Config path and connection params are forwarded to install_hooks."""
        path = tmp_path / "settings.json"
        path.write_text("{}\n")

        with (
            patch("agent_smith.install.sys.stdin") as mock_stdin,
            patch("agent_smith.install.sys.stdout") as mock_stdout,
            patch("agent_smith.install.show_in_pager"),
            patch("agent_smith.install.confirm_apply", return_value=True),
        ):
            mock_stdin.isatty.return_value = True
            mock_stdout.isatty.return_value = True

            run_install(
                str(path),
                config_path="/etc/agent-smith.env",
                homeserver="https://matrix.example.org",
            )

        result = json.loads(path.read_text())
        stop_cmd = result["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert "-c /etc/agent-smith.env" in stop_cmd
        assert "--homeserver https://matrix.example.org" in stop_cmd

    def test_prints_confirmation_message_on_apply(self, tmp_path):
        """Prints the destination path after writing."""
        path = tmp_path / "settings.json"
        path.write_text("{}\n")

        with (
            patch("agent_smith.install.sys.stdin") as mock_stdin,
            patch("agent_smith.install.sys.stdout") as mock_stdout,
            patch("agent_smith.install.show_in_pager"),
            patch("agent_smith.install.confirm_apply", return_value=True),
            patch("builtins.print") as mock_print,
        ):
            mock_stdin.isatty.return_value = True
            mock_stdout.isatty.return_value = True

            run_install(str(path))

        printed = " ".join(str(a) for c in mock_print.call_args_list for a in c[0])
        assert "Changes written to" in printed
        assert str(path) in printed

    def test_prints_rejection_message_on_decline(self, tmp_path):
        """Prints a message when the user declines."""
        path = tmp_path / "settings.json"
        path.write_text("{}\n")

        with (
            patch("agent_smith.install.sys.stdin") as mock_stdin,
            patch("agent_smith.install.sys.stdout") as mock_stdout,
            patch("agent_smith.install.show_in_pager"),
            patch("agent_smith.install.confirm_apply", return_value=False),
            patch("builtins.print") as mock_print,
        ):
            mock_stdin.isatty.return_value = True
            mock_stdout.isatty.return_value = True

            run_install(str(path))

        printed = " ".join(str(a) for c in mock_print.call_args_list for a in c[0])
        assert "No changes applied." in printed
