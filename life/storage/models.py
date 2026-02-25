from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SceneType(Enum):
    DARK = "dark"
    NORMAL = "normal"
    BRIGHT = "bright"


# Analysis time scales
SCALES = {
    "10m": 600,
    "30m": 1800,
    "1h": 3600,
    "6h": 21600,
    "12h": 43200,
    "24h": 86400,
}


@dataclass
class Frame:
    id: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    path: str = ""
    screen_path: str = ""
    audio_path: str = ""
    transcription: str = ""
    brightness: float = 0.0
    motion_score: float = 0.0
    scene_type: SceneType = SceneType.NORMAL
    claude_description: str = ""
    activity: str = ""
    screen_extra_paths: str = ""  # comma-separated extra screen paths


@dataclass
class Event:
    id: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = ""  # motion_spike, scene_change
    description: str = ""
    frame_id: int | None = None


@dataclass
class Summary:
    id: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    scale: str = ""  # 10m, 30m, 1h, 6h, 12h, 24h
    content: str = ""
    frame_count: int = 0
