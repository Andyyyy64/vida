from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DATA_DIR = Path("data")
DEFAULT_CONFIG_PATH = Path("life.toml")


@dataclass
class CaptureConfig:
    device: int = 0
    interval_sec: int = 30
    width: int = 640
    height: int = 480
    jpeg_quality: int = 85
    screen_burst_count: int = 3
    audio_device: str = ""  # ALSA device, e.g. "plughw:1,0". Empty = auto-detect
    audio_sample_rate: int = 44100


@dataclass
class AnalysisConfig:
    motion_threshold: float = 0.02
    brightness_dark: float = 40.0
    brightness_bright: float = 180.0


@dataclass
class LLMConfig:
    provider: str = "claude"
    claude_model: str = "haiku"
    codex_model: str = "gpt-5.4"
    gemini_model: str = "gemini-3.1-flash-lite-preview"


@dataclass
class PresenceConfig:
    enabled: bool = True
    absent_threshold_ticks: int = 3  # consecutive ticks before state change
    sleep_start_hour: int = 23
    sleep_end_hour: int = 8


@dataclass
class NotifyConfig:
    provider: str = ""  # "discord" or "line"
    webhook_url: str = ""
    enabled: bool = False


@dataclass
class DiscordChatConfig:
    enabled: bool = False
    user_token: str = ""
    user_id: str = ""  # Your Discord user ID (to identify own messages)
    poll_interval: int = 60  # seconds between polls
    backfill_months: int = 3  # fetch past N months on first run (0 = no backfill)


@dataclass
class EmbeddingConfig:
    enabled: bool = True
    model: str = "gemini-embedding-2-preview"
    dimensions: int = 3072


@dataclass
class ChatConfig:
    enabled: bool = False
    discord: DiscordChatConfig = field(default_factory=DiscordChatConfig)


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: DEFAULT_DATA_DIR)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    presence: PresenceConfig = field(default_factory=PresenceConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chat: ChatConfig = field(default_factory=ChatConfig)
    knowledge_interval_days: int = 7
    retention_days: int = 90
    pid_file: Path = field(default_factory=lambda: DEFAULT_DATA_DIR / "life.pid")
    db_path: Path = field(default_factory=lambda: DEFAULT_DATA_DIR / "life.db")

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        # Load .env file (secrets like API keys and tokens)
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        path = path or DEFAULT_CONFIG_PATH
        if not path.exists():
            return cls()
        with open(path, "rb") as f:
            data = tomllib.load(f)
        cfg = cls()
        if "data_dir" in data:
            cfg.data_dir = Path(data["data_dir"])
            cfg.pid_file = cfg.data_dir / "life.pid"
            cfg.db_path = cfg.data_dir / "life.db"
        if "capture" in data:
            for k, v in data["capture"].items():
                if hasattr(cfg.capture, k):
                    setattr(cfg.capture, k, type(getattr(cfg.capture, k))(v))
        if "analysis" in data:
            for k, v in data["analysis"].items():
                if hasattr(cfg.analysis, k):
                    setattr(cfg.analysis, k, type(getattr(cfg.analysis, k))(v))
        if "llm" in data:
            for k, v in data["llm"].items():
                if hasattr(cfg.llm, k):
                    setattr(cfg.llm, k, str(v))
        if "presence" in data:
            for k, v in data["presence"].items():
                if hasattr(cfg.presence, k):
                    setattr(cfg.presence, k, type(getattr(cfg.presence, k))(v))
        if "notify" in data:
            for k, v in data["notify"].items():
                if hasattr(cfg.notify, k):
                    if k == "enabled":
                        cfg.notify.enabled = bool(v)
                    else:
                        setattr(cfg.notify, k, str(v))
        if "embedding" in data:
            emb = data["embedding"]
            if isinstance(emb.get("enabled"), bool):
                cfg.embedding.enabled = emb["enabled"]
            if "model" in emb:
                cfg.embedding.model = str(emb["model"])
            if "dimensions" in emb:
                cfg.embedding.dimensions = int(emb["dimensions"])
        if "knowledge_interval_days" in data:
            cfg.knowledge_interval_days = int(data["knowledge_interval_days"])
        if "retention_days" in data:
            cfg.retention_days = int(data["retention_days"])
        if "chat" in data:
            chat_data = data["chat"]
            if isinstance(chat_data.get("enabled"), bool):
                cfg.chat.enabled = chat_data["enabled"]
            if "discord" in chat_data:
                d = chat_data["discord"]
                if isinstance(d.get("enabled"), bool):
                    cfg.chat.discord.enabled = d["enabled"]
                for k in ("user_token", "user_id"):
                    if k in d:
                        setattr(cfg.chat.discord, k, str(d[k]))
                if "poll_interval" in d:
                    cfg.chat.discord.poll_interval = int(d["poll_interval"])
                if "backfill_months" in d:
                    cfg.chat.discord.backfill_months = int(d["backfill_months"])
        # Secrets: env vars override TOML (keep secrets out of life.toml)
        cfg._load_env_secrets()
        return cfg

    @classmethod
    def load_from_db(cls, db_path: Path) -> Config:
        """Load config from the settings table in SQLite."""
        import sqlite3

        cfg = cls()
        cfg.db_path = db_path
        cfg.data_dir = db_path.parent
        cfg.pid_file = cfg.data_dir / "life.pid"

        if not db_path.exists():
            return cfg

        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        except sqlite3.OperationalError:
            conn.close()
            return cfg
        conn.close()

        s = {k: v for k, v in rows}

        # LLM
        if v := s.get("llm.provider"):
            cfg.llm.provider = v
        if v := s.get("llm.gemini_model"):
            cfg.llm.gemini_model = v
        if v := s.get("llm.claude_model"):
            cfg.llm.claude_model = v
        if v := s.get("llm.codex_model"):
            cfg.llm.codex_model = v
        # Capture
        if v := s.get("capture.device"):
            cfg.capture.device = int(v)
        if v := s.get("capture.interval_sec"):
            cfg.capture.interval_sec = int(v)
        if v := s.get("capture.audio_device"):
            cfg.capture.audio_device = v
        # Presence
        if v := s.get("presence.enabled"):
            cfg.presence.enabled = v == "true"
        if v := s.get("presence.sleep_start_hour"):
            cfg.presence.sleep_start_hour = int(v)
        if v := s.get("presence.sleep_end_hour"):
            cfg.presence.sleep_end_hour = int(v)
        # Embedding
        if v := s.get("embedding.enabled"):
            cfg.embedding.enabled = v == "true"
        if v := s.get("embedding.model"):
            cfg.embedding.model = v
        if v := s.get("embedding.dimensions"):
            cfg.embedding.dimensions = int(v)
        # Chat
        if v := s.get("chat.enabled"):
            cfg.chat.enabled = v == "true"
        if v := s.get("chat.discord.enabled"):
            cfg.chat.discord.enabled = v == "true"
        if v := s.get("chat.discord.poll_interval"):
            cfg.chat.discord.poll_interval = int(v)
        if v := s.get("chat.discord.backfill_months"):
            cfg.chat.discord.backfill_months = int(v)
        # Notify
        if v := s.get("notify.enabled"):
            cfg.notify.enabled = v == "true"
        if v := s.get("notify.provider"):
            cfg.notify.provider = v
        if v := s.get("notify.webhook_url"):
            cfg.notify.webhook_url = v
        # Top-level
        if v := s.get("knowledge_interval_days"):
            cfg.knowledge_interval_days = int(v)
        if v := s.get("retention_days"):
            cfg.retention_days = int(v)

        # Inject secrets into os.environ for LLM/embedding modules
        env_keys = ["GEMINI_API_KEY", "DISCORD_USER_TOKEN", "DISCORD_USER_ID", "NOTIFY_WEBHOOK_URL"]
        for ek in env_keys:
            if v := s.get(f"env.{ek}"):
                os.environ[ek] = v

        # Also populate config fields from env
        cfg._load_env_secrets()
        return cfg

    def _load_env_secrets(self) -> None:
        """Load secrets from environment variables (.env). Env vars take priority over TOML."""
        if v := os.environ.get("DISCORD_USER_TOKEN"):
            self.chat.discord.user_token = v
        if v := os.environ.get("DISCORD_USER_ID"):
            self.chat.discord.user_id = v
        if v := os.environ.get("NOTIFY_WEBHOOK_URL"):
            self.notify.webhook_url = v
