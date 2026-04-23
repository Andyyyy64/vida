"""Tests for daemon.config — Config loading from TOML."""

from __future__ import annotations

from pathlib import Path

import pytest

from daemon.config import Config

# ---------------------------------------------------------------------------
# Default config (no file)
# ---------------------------------------------------------------------------

class TestDefaultConfig:
    def test_default_when_no_file(self, tmp_path):
        """Config.load returns defaults when TOML file does not exist."""
        cfg = Config.load(tmp_path / "nonexistent.toml")

        assert cfg.data_dir == Path("data")
        assert cfg.db_path == Path("data/life.db")
        assert cfg.pid_file == Path("data/life.pid")

    def test_default_capture(self, tmp_path):
        cfg = Config.load(tmp_path / "nonexistent.toml")
        assert cfg.capture.device == 0
        assert cfg.capture.interval_sec == 30
        assert cfg.capture.width == 640
        assert cfg.capture.height == 480
        assert cfg.capture.jpeg_quality == 85
        assert cfg.capture.screen_burst_count == 3

    def test_default_analysis(self, tmp_path):
        cfg = Config.load(tmp_path / "nonexistent.toml")
        assert cfg.analysis.motion_threshold == pytest.approx(0.02)
        assert cfg.analysis.brightness_dark == pytest.approx(40.0)
        assert cfg.analysis.brightness_bright == pytest.approx(180.0)

    def test_default_llm(self, tmp_path):
        cfg = Config.load(tmp_path / "nonexistent.toml")
        assert cfg.llm.provider == "claude"
        assert cfg.llm.claude_model == "haiku"
        assert cfg.llm.codex_model == "gpt-5.4"

    def test_default_presence(self, tmp_path):
        cfg = Config.load(tmp_path / "nonexistent.toml")
        assert cfg.presence.enabled is True
        assert cfg.presence.absent_threshold_ticks == 3
        assert cfg.presence.sleep_start_hour == 23
        assert cfg.presence.sleep_end_hour == 8

    def test_default_notify(self, tmp_path):
        cfg = Config.load(tmp_path / "nonexistent.toml")
        assert cfg.notify.enabled is False
        assert cfg.notify.provider == ""
        assert cfg.notify.webhook_url == ""

    def test_default_chat(self, tmp_path):
        cfg = Config.load(tmp_path / "nonexistent.toml")
        assert cfg.chat.enabled is False
        assert cfg.chat.discord.enabled is False


# ---------------------------------------------------------------------------
# Load from TOML file
# ---------------------------------------------------------------------------

class TestLoadFromToml:
    def test_loads_data_dir(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text('data_dir = "/custom/data"\n')

        cfg = Config.load(toml_path)
        assert cfg.data_dir == Path("/custom/data")
        assert cfg.db_path == Path("/custom/data/life.db")
        assert cfg.pid_file == Path("/custom/data/life.pid")

    def test_loads_capture_config(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            "[capture]\n"
            "device = 2\n"
            "interval_sec = 60\n"
            "width = 1280\n"
            "height = 720\n"
            "jpeg_quality = 90\n"
            "screen_burst_count = 5\n"
        )

        cfg = Config.load(toml_path)
        assert cfg.capture.device == 2
        assert cfg.capture.interval_sec == 60
        assert cfg.capture.width == 1280
        assert cfg.capture.height == 720
        assert cfg.capture.jpeg_quality == 90
        assert cfg.capture.screen_burst_count == 5

    def test_loads_analysis_config(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            "[analysis]\n"
            "motion_threshold = 0.05\n"
            "brightness_dark = 30.0\n"
            "brightness_bright = 200.0\n"
        )

        cfg = Config.load(toml_path)
        assert cfg.analysis.motion_threshold == pytest.approx(0.05)
        assert cfg.analysis.brightness_dark == pytest.approx(30.0)
        assert cfg.analysis.brightness_bright == pytest.approx(200.0)

    def test_loads_llm_config(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            "[llm]\n"
            'provider = "gemini"\n'
            'claude_model = "sonnet"\n'
            'codex_model = "gpt-5.4-mini"\n'
            'gemini_model = "gemini-pro"\n'
        )

        cfg = Config.load(toml_path)
        assert cfg.llm.provider == "gemini"
        assert cfg.llm.claude_model == "sonnet"
        assert cfg.llm.codex_model == "gpt-5.4-mini"
        assert cfg.llm.gemini_model == "gemini-pro"

    def test_loads_presence_config(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            "[presence]\n"
            "enabled = false\n"
            "absent_threshold_ticks = 5\n"
            "sleep_start_hour = 22\n"
            "sleep_end_hour = 7\n"
        )

        cfg = Config.load(toml_path)
        assert cfg.presence.enabled is False
        assert cfg.presence.absent_threshold_ticks == 5
        assert cfg.presence.sleep_start_hour == 22
        assert cfg.presence.sleep_end_hour == 7

    def test_loads_notify_config(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            "[notify]\n"
            'provider = "discord"\n'
            'webhook_url = "https://discord.com/webhook/123"\n'
            "enabled = true\n"
        )

        cfg = Config.load(toml_path)
        assert cfg.notify.provider == "discord"
        assert cfg.notify.webhook_url == "https://discord.com/webhook/123"
        assert cfg.notify.enabled is True

    def test_loads_chat_config(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            "[chat]\n"
            "enabled = true\n"
            "\n"
            "[chat.discord]\n"
            "enabled = true\n"
            'user_token = "test_token"\n'
            'user_id = "12345"\n'
            "poll_interval = 120\n"
            "backfill_months = 6\n"
        )

        cfg = Config.load(toml_path)
        assert cfg.chat.enabled is True
        assert cfg.chat.discord.enabled is True
        assert cfg.chat.discord.user_token == "test_token"
        assert cfg.chat.discord.user_id == "12345"
        assert cfg.chat.discord.poll_interval == 120
        assert cfg.chat.discord.backfill_months == 6

    def test_loads_knowledge_interval(self, tmp_path):
        toml_path = tmp_path / "test.toml"
        toml_path.write_text("knowledge_interval_days = 14\n")

        cfg = Config.load(toml_path)
        assert cfg.knowledge_interval_days == 14

    def test_partial_config_uses_defaults(self, tmp_path):
        """Only specified fields are overridden; rest keep defaults."""
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            "[capture]\n"
            "interval_sec = 120\n"
        )

        cfg = Config.load(toml_path)
        assert cfg.capture.interval_sec == 120
        # Other capture fields should be defaults
        assert cfg.capture.device == 0
        assert cfg.capture.width == 640

    def test_unknown_keys_ignored(self, tmp_path):
        """Unknown config keys should not cause errors."""
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            "[capture]\n"
            "unknown_key = 42\n"
            "interval_sec = 60\n"
        )

        cfg = Config.load(toml_path)
        assert cfg.capture.interval_sec == 60
        assert not hasattr(cfg.capture, "unknown_key")


# ---------------------------------------------------------------------------
# Environment variable secrets
# ---------------------------------------------------------------------------

class TestEnvSecrets:
    """Env secrets are only loaded when a TOML file exists (Config.load returns
    early with bare defaults when the file is missing, skipping _load_env_secrets).
    So these tests use a minimal TOML file to trigger the full load path."""

    def _write_minimal_toml(self, tmp_path) -> Path:
        toml_path = tmp_path / "test.toml"
        toml_path.write_text("")  # empty but existing file
        return toml_path

    def test_discord_token_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_USER_TOKEN", "env_token_123")

        cfg = Config.load(self._write_minimal_toml(tmp_path))
        assert cfg.chat.discord.user_token == "env_token_123"

    def test_discord_user_id_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISCORD_USER_ID", "env_user_456")

        cfg = Config.load(self._write_minimal_toml(tmp_path))
        assert cfg.chat.discord.user_id == "env_user_456"

    def test_notify_webhook_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://hooks.example.com/abc")

        cfg = Config.load(self._write_minimal_toml(tmp_path))
        assert cfg.notify.webhook_url == "https://hooks.example.com/abc"

    def test_env_overrides_toml(self, tmp_path, monkeypatch):
        """Env vars take priority over TOML values."""
        toml_path = tmp_path / "test.toml"
        toml_path.write_text(
            "[chat]\n"
            "enabled = true\n"
            "[chat.discord]\n"
            'user_token = "toml_token"\n'
        )
        monkeypatch.setenv("DISCORD_USER_TOKEN", "env_token_wins")

        cfg = Config.load(toml_path)
        assert cfg.chat.discord.user_token == "env_token_wins"

    def test_no_env_secrets_when_file_missing(self, tmp_path, monkeypatch):
        """When TOML file doesn't exist, Config.load returns bare defaults
        without calling _load_env_secrets (by design)."""
        monkeypatch.setenv("DISCORD_USER_TOKEN", "should_not_appear")

        cfg = Config.load(tmp_path / "nonexistent.toml")
        # _load_env_secrets is NOT called, so env vars are not loaded
        assert cfg.chat.discord.user_token == ""
