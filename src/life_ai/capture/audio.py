from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


class AudioCapture:
    """Capture audio using arecord (ALSA) for a given duration."""

    def __init__(self, data_dir: Path, device: str = "plughw:1,0", sample_rate: int = 16000):
        self._data_dir = data_dir
        self._device = device
        self._sample_rate = sample_rate

    def capture(self, duration_sec: int = 30, timestamp: datetime | None = None) -> str | None:
        """Record audio and save as WAV. Returns relative path or None."""
        timestamp = timestamp or datetime.now()
        date_dir = self._data_dir / "audio" / timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        filename = timestamp.strftime("%H-%M-%S") + ".wav"
        filepath = date_dir / filename

        try:
            result = subprocess.run(
                [
                    "arecord",
                    "-D", self._device,
                    "-f", "S16_LE",
                    "-r", str(self._sample_rate),
                    "-c", "1",
                    "-d", str(duration_sec),
                    "-q",
                    str(filepath),
                ],
                capture_output=True,
                text=True,
                timeout=duration_sec + 10,
            )
            if result.returncode != 0:
                log.warning("arecord failed: %s", result.stderr[:200])
                return None
            if not filepath.exists() or filepath.stat().st_size < 100:
                log.warning("Audio file too small or missing: %s", filepath)
                return None
            rel_path = str(filepath.relative_to(self._data_dir))
            log.debug("Audio captured: %s", rel_path)
            return rel_path
        except subprocess.TimeoutExpired:
            log.warning("Audio capture timed out")
            return None
        except FileNotFoundError:
            log.warning("arecord not found (install alsa-utils)")
            return None
        except Exception:
            log.exception("Audio capture error")
            return None

    def get_disk_usage(self) -> int:
        audio_dir = self._data_dir / "audio"
        if not audio_dir.exists():
            return 0
        return sum(f.stat().st_size for f in audio_dir.rglob("*.wav"))
