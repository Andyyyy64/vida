from __future__ import annotations

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


@dataclass
class AnalysisConfig:
    motion_threshold: float = 0.02
    brightness_dark: float = 40.0
    brightness_bright: float = 180.0


@dataclass
class LLMConfig:
    provider: str = "claude"
    claude_model: str = "haiku"
    gemini_model: str = "gemini-2.5-flash"


@dataclass
class NotifyConfig:
    provider: str = ""  # "discord" or "line"
    webhook_url: str = ""
    enabled: bool = False


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: DEFAULT_DATA_DIR)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    pid_file: Path = field(default_factory=lambda: DEFAULT_DATA_DIR / "life.pid")
    db_path: Path = field(default_factory=lambda: DEFAULT_DATA_DIR / "life.db")

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
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
        if "notify" in data:
            for k, v in data["notify"].items():
                if hasattr(cfg.notify, k):
                    if k == "enabled":
                        cfg.notify.enabled = bool(v)
                    else:
                        setattr(cfg.notify, k, str(v))
        return cfg
