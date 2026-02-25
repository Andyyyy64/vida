from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


class FrameStore:
    def __init__(self, data_dir: Path, jpeg_quality: int = 85):
        self._data_dir = data_dir
        self._jpeg_quality = jpeg_quality

    def save(self, frame: np.ndarray, timestamp: datetime | None = None) -> str:
        timestamp = timestamp or datetime.now()
        date_dir = self._data_dir / "frames" / timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        filename = timestamp.strftime("%H-%M-%S") + ".jpg"
        filepath = date_dir / filename
        cv2.imwrite(
            str(filepath),
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
        )
        rel_path = str(filepath.relative_to(self._data_dir))
        log.debug("Saved frame: %s", rel_path)
        return rel_path

    def get_disk_usage(self) -> int:
        frames_dir = self._data_dir / "frames"
        if not frames_dir.exists():
            return 0
        return sum(f.stat().st_size for f in frames_dir.rglob("*.jpg"))

    def get_frame_count_today(self) -> int:
        today_dir = self._data_dir / "frames" / datetime.now().strftime("%Y-%m-%d")
        if not today_dir.exists():
            return 0
        return len(list(today_dir.glob("*.jpg")))
