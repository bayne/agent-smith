"""Tests for agent_smith.main."""

import io
from unittest.mock import AsyncMock, patch

import pytest

from agent_smith.main import (
    format_notify_message,
    format_stop_message,
    get_config,
    load_config_file,
    read_stdin_json,
    send_message,
)


class TestGetConfig:
    def test_returns_config_when_all_vars_set(self, monkeypatch):
        monkeypatch.setenv("MATRIX_HOMESERVER", "https://matrix.example.org")
        monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "syt_test_token")
        monkeypatch.setenv("MATRIX_ROOM_ID", "!abc:example.org")

        config = get_config()
        assert config == {
            "MATRIX_HOMESERVER": "https://matrix.example.org",
            "MATRIX_ACCESS_TOKEN": "syt_test_token",
            "MATRIX_ROOM_ID": "!abc:example.org",
        }

    def test_raises_when_all_vars_missing(self, monkeypatch):
        monkeypatch.delenv("MATRIX_HOMESERVER", raising=False)
        monkeypatch.delenv("MATRIX_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MATRIX_ROOM_ID", raising=False)

        with pytest.raises(ValueError, match="Missing required environment variables"):
            get_config()

    def test_raises_when_one_var_missing(self, monkeypatch):
        monkeypatch.setenv("MATRIX_HOMESERVER", "https://matrix.example.org")
        monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "syt_test_token")
        monkeypatch.delenv("MATRIX_ROOM_ID", raising=False)

        with pytest.raises(ValueError, match="MATRIX_ROOM_ID"):
            get_config()

    def test_overrides_take_precedence_over_env(self, monkeypatch):
        monkeypatch.setenv("MATRIX_HOMESERVER", "https://env.example.org")
        monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "env_token")
        monkeypatch.setenv("MATRIX_ROOM_ID", "!env:example.org")

        config = get_config({
            "MATRIX_HOMESERVER": "https://cli.example.org",
            "MATRIX_ROOM_ID": "!cli:example.org",
        })
        assert config["MATRIX_HOMESERVER"] == "https://cli.example.org"
        assert config["MATRIX_ACCESS_TOKEN"] == "env_token"
        assert config["MATRIX_ROOM_ID"] == "!cli:example.org"

    def test_overrides_fill_missing_env(self, monkeypatch):
        monkeypatch.delenv("MATRIX_HOMESERVER", raising=False)
        monkeypatch.delenv("MATRIX_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MATRIX_ROOM_ID", raising=False)

        config = get_config({
            "MATRIX_HOMESERVER": "https://cli.example.org",
            "MATRIX_ACCESS_TOKEN": "cli_token",
            "MATRIX_ROOM_ID": "!cli:example.org",
        })
        assert config == {
            "MATRIX_HOMESERVER": "https://cli.example.org",
            "MATRIX_ACCESS_TOKEN": "cli_token",
            "MATRIX_ROOM_ID": "!cli:example.org",
        }


class TestLoadConfigFile:
    def test_loads_matrix_vars_from_file(self, tmp_path):
        cfg = tmp_path / "matrix.env"
        cfg.write_text(
            "MATRIX_HOMESERVER=https://file.example.org\n"
            "MATRIX_ACCESS_TOKEN=file_token\n"
            "MATRIX_ROOM_ID=!file:example.org\n"
        )
        result = load_config_file(str(cfg))
        assert result == {
            "MATRIX_HOMESERVER": "https://file.example.org",
            "MATRIX_ACCESS_TOKEN": "file_token",
            "MATRIX_ROOM_ID": "!file:example.org",
        }

    def test_ignores_non_matrix_vars(self, tmp_path):
        cfg = tmp_path / "matrix.env"
        cfg.write_text(
            "MATRIX_HOMESERVER=https://file.example.org\n"
            "MATRIX_ACCESS_TOKEN=file_token\n"
            "MATRIX_ROOM_ID=!file:example.org\n"
            "OTHER_VAR=should_be_ignored\n"
        )
        result = load_config_file(str(cfg))
        assert "OTHER_VAR" not in result
        assert len(result) == 3

    def test_config_file_feeds_into_get_config(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MATRIX_HOMESERVER", raising=False)
        monkeypatch.delenv("MATRIX_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MATRIX_ROOM_ID", raising=False)

        cfg = tmp_path / "matrix.env"
        cfg.write_text(
            "MATRIX_HOMESERVER=https://file.example.org\n"
            "MATRIX_ACCESS_TOKEN=file_token\n"
            "MATRIX_ROOM_ID=!file:example.org\n"
        )
        overrides = load_config_file(str(cfg))
        config = get_config(overrides)
        assert config["MATRIX_HOMESERVER"] == "https://file.example.org"


class TestSendMessage:
    @pytest.mark.anyio
    async def test_sends_message_and_returns_confirmation(self, monkeypatch):
        monkeypatch.setenv("MATRIX_HOMESERVER", "https://matrix.example.org")
        monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "syt_test_token")
        monkeypatch.setenv("MATRIX_ROOM_ID", "!abc:example.org")

        mock_send = AsyncMock()
        with patch("agent_smith.main.send_matrix_message", mock_send):
            result = await send_message(message="Hello Matrix!")

        assert result == "Message sent"
        mock_send.assert_called_once()
        config_arg, body_arg = mock_send.call_args.args
        assert config_arg["MATRIX_ROOM_ID"] == "!abc:example.org"
        assert body_arg == "Hello Matrix!"

    @pytest.mark.anyio
    async def test_raises_on_missing_config(self, monkeypatch):
        monkeypatch.delenv("MATRIX_HOMESERVER", raising=False)
        monkeypatch.delenv("MATRIX_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MATRIX_ROOM_ID", raising=False)

        with pytest.raises(ValueError, match="Missing required environment variables"):
            await send_message(message="Hello Matrix!")

    @pytest.mark.anyio
    async def test_propagates_matrix_errors(self, monkeypatch):
        monkeypatch.setenv("MATRIX_HOMESERVER", "https://matrix.example.org")
        monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "syt_test_token")
        monkeypatch.setenv("MATRIX_ROOM_ID", "!abc:example.org")

        mock_send = AsyncMock(side_effect=RuntimeError("Matrix send failed"))
        with patch("agent_smith.main.send_matrix_message", mock_send):
            with pytest.raises(RuntimeError, match="Matrix send failed"):
                await send_message(message="Hello Matrix!")


class TestFormatStopMessage:
    def test_normal_case(self):
        data = {"session_id": "abc12345xyz", "cwd": "/home/user/myproject"}
        result = format_stop_message(data)
        assert result == "Task complete in **myproject** (session `abc12345`)"

    def test_stop_hook_active_returns_none(self):
        data = {"session_id": "abc12345", "cwd": "/tmp", "stop_hook_active": True}
        assert format_stop_message(data) is None

    def test_stop_hook_active_false_sends(self):
        data = {"session_id": "abc12345", "cwd": "/tmp/proj", "stop_hook_active": False}
        result = format_stop_message(data)
        assert result is not None
        assert "proj" in result

    def test_missing_fields_use_defaults(self):
        result = format_stop_message({})
        assert result == "Task complete in **unknown** (session `unknown`)"

    def test_session_id_truncated_to_eight(self):
        data = {"session_id": "abcdefghijklmnop", "cwd": "/tmp/x"}
        result = format_stop_message(data)
        assert "`abcdefgh`" in result


class TestFormatNotifyMessage:
    def test_permission_prompt(self):
        data = {
            "notification_type": "permission_prompt",
            "message": "Allow file write?",
            "cwd": "/home/user/proj",
        }
        result = format_notify_message(data)
        assert result == "Permission needed in **proj**: Allow file write?"

    def test_idle_prompt(self):
        data = {
            "notification_type": "idle_prompt",
            "message": "Waiting",
            "cwd": "/tmp/proj",
        }
        result = format_notify_message(data)
        assert "Waiting for input" in result

    def test_elicitation_dialog(self):
        data = {
            "notification_type": "elicitation_dialog",
            "message": "Pick one",
            "cwd": "/tmp/proj",
        }
        assert "Question for you" in format_notify_message(data)

    def test_unknown_type_fallback(self):
        data = {
            "notification_type": "something_new",
            "message": "Hello",
            "cwd": "/tmp/proj",
        }
        assert "Notification" in format_notify_message(data)

    def test_with_title(self):
        data = {
            "notification_type": "permission_prompt",
            "message": "Allow?",
            "title": "Bash Command",
            "cwd": "/tmp/proj",
        }
        result = format_notify_message(data)
        assert result == "Permission needed in **proj** — Bash Command: Allow?"

    def test_missing_fields_use_defaults(self):
        result = format_notify_message({})
        assert result == "Notification in **unknown**: Input needed"


class TestReadStdinJson:
    def test_valid_json(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO('{"key": "value"}'))
        assert read_stdin_json() == {"key": "value"}

    def test_invalid_json_raises(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
        with pytest.raises(Exception):
            read_stdin_json()
