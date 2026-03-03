from __future__ import annotations

import logging
import os
import re
import shlex
import struct
import subprocess
import sys
import wave
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


def _detect_alsa_device() -> str:
    """Auto-detect the best ALSA capture device, preferring non-webcam mics."""
    try:
        result = subprocess.run(
            ["arecord", "-l"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return "plughw:0,0"

        # Parse "card N: NAME [DESC], device M: ..."
        cards: list[tuple[int, int, str]] = []
        for line in result.stdout.splitlines():
            m = re.match(r"card (\d+):.*\[(.+?)\].*device (\d+):", line)
            if m:
                card, name, dev = int(m.group(1)), m.group(2), int(m.group(3))
                cards.append((card, dev, name))

        if not cards:
            return "plughw:0,0"

        # Prefer non-webcam devices (webcams usually have "CAM" or "C270" etc.)
        webcam_keywords = {"webcam", "cam", "c270", "c920", "c922", "brio"}
        non_webcam = [
            (c, d, n) for c, d, n in cards
            if not any(kw in n.lower() for kw in webcam_keywords)
        ]
        if non_webcam:
            card, dev, name = non_webcam[0]
            log.info("Auto-detected audio device: plughw:%d,%d (%s)", card, dev, name)
            return f"plughw:{card},{dev}"

        card, dev, name = cards[0]
        log.info("Using first audio device: plughw:%d,%d (%s)", card, dev, name)
        return f"plughw:{card},{dev}"

    except Exception:
        log.warning("Audio device detection failed, using plughw:0,0")
        return "plughw:0,0"


def _trim_silence(filepath: Path, threshold: int = 500, min_voice_sec: float = 0.3) -> bool:
    """Trim leading/trailing silence from a WAV file in-place.

    Returns True if the file contains speech, False if mostly silent.
    """
    try:
        with wave.open(str(filepath), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sampwidth != 2:
            return True  # only handle 16-bit

        # Convert to absolute sample values
        fmt = f"<{n_frames * n_channels}h"
        samples = struct.unpack(fmt, raw)

        # For stereo, take max of channels per frame
        if n_channels == 2:
            mono = [max(abs(samples[i]), abs(samples[i + 1])) for i in range(0, len(samples), 2)]
        else:
            mono = [abs(s) for s in samples]

        # Find first and last sample above threshold
        first_voice = -1
        last_voice = -1
        for i, v in enumerate(mono):
            if v > threshold:
                if first_voice < 0:
                    first_voice = i
                last_voice = i

        if first_voice < 0:
            return False  # all silence

        voice_duration = (last_voice - first_voice) / framerate
        if voice_duration < min_voice_sec:
            return False  # too short to be meaningful speech

        # Add 0.2s padding around voice
        pad_frames = int(framerate * 0.2)
        start = max(0, first_voice - pad_frames)
        end = min(len(mono), last_voice + pad_frames)

        # Write trimmed audio
        if n_channels == 2:
            trimmed_raw = raw[start * 2 * sampwidth : end * 2 * sampwidth]
        else:
            trimmed_raw = raw[start * sampwidth : end * sampwidth]

        with wave.open(str(filepath), "wb") as wf:
            wf.setnchannels(n_channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(framerate)
            wf.writeframes(trimmed_raw)

        trimmed_duration = (end - start) / framerate
        log.debug("Trimmed audio: %.1fs → %.1fs", n_frames / framerate, trimmed_duration)
        return True

    except Exception:
        log.debug("Silence trimming failed, keeping original", exc_info=True)
        return True  # keep file on error


class AudioCapture:
    """Capture audio for a given duration.

    Uses sounddevice (CoreAudio) on macOS, arecord (ALSA) on Linux/WSL2.
    """

    def __init__(self, data_dir: Path, device: str = "", sample_rate: int = 44100):
        self._data_dir = data_dir
        self._sample_rate = sample_rate
        if sys.platform == "linux":
            # ALSA device string (e.g. "plughw:1,0"). Empty = auto-detect.
            self._alsa_device = device or _detect_alsa_device()
            self._sd_device: str | None = None
        else:
            # sounddevice device name (substring match). Empty = system default.
            self._alsa_device = ""
            self._sd_device = device or None

    def capture(self, duration_sec: int = 30, timestamp: datetime | None = None) -> str | None:
        """Record audio and save as WAV. Returns relative path or None."""
        timestamp = timestamp or datetime.now()
        date_dir = self._data_dir / "audio" / timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        filename = timestamp.strftime("%H-%M-%S") + ".wav"
        filepath = date_dir / filename

        if sys.platform in ("darwin", "win32"):
            ok = self._capture_sounddevice(filepath, duration_sec)
        else:
            ok = self._capture_alsa(filepath, duration_sec)

        if not ok:
            return None

        has_voice = _trim_silence(filepath)
        if not has_voice:
            log.debug("No voice detected in %s, removing", filepath)
            filepath.unlink(missing_ok=True)
            return None

        rel_path = str(filepath.relative_to(self._data_dir))
        log.debug("Audio captured: %s", rel_path)
        return rel_path

    def _capture_sounddevice(self, filepath: Path, duration_sec: int) -> bool:
        """Record using sounddevice (CoreAudio on Mac, WASAPI on Windows)."""
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            log.warning("sounddevice not installed. Run: pip install sounddevice")
            return False

        try:
            recording = sd.rec(
                int(duration_sec * self._sample_rate),
                samplerate=self._sample_rate,
                channels=1,
                dtype="int16",
                device=self._sd_device,  # None = system default
            )
            sd.wait()

            with wave.open(str(filepath), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self._sample_rate)
                wf.writeframes(recording.tobytes())

            if not filepath.exists() or filepath.stat().st_size < 100:
                log.warning("Audio file too small or missing: %s", filepath)
                return False
            return True
        except Exception:
            log.exception("Audio capture error (sounddevice)")
            return False

    def _capture_alsa(self, filepath: Path, duration_sec: int) -> bool:
        """Record using arecord (ALSA) for Linux/WSL2."""
        try:
            import grp
            cmd = [
                "arecord",
                "-D", self._alsa_device,
                "-f", "S16_LE",
                "-r", str(self._sample_rate),
                "-c", "1",
                "-d", str(duration_sec),
                "-q",
                str(filepath),
            ]
            # If current process is not in audio group, use sg to acquire it
            if not self._in_audio_group():
                cmd = ["sg", "audio", "-c", " ".join(shlex.quote(c) for c in cmd)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration_sec + 10,
            )
            if result.returncode != 0:
                log.warning("arecord failed: %s", result.stderr[:200])
                return False
            if not filepath.exists() or filepath.stat().st_size < 100:
                log.warning("Audio file too small or missing: %s", filepath)
                return False
            return True
        except subprocess.TimeoutExpired:
            log.warning("Audio capture timed out")
            return False
        except FileNotFoundError:
            log.warning("arecord not found (install alsa-utils)")
            return False
        except Exception:
            log.exception("Audio capture error")
            return False

    @staticmethod
    def _in_audio_group() -> bool:
        try:
            import grp
            audio_gid = grp.getgrnam("audio").gr_gid
            return audio_gid in os.getgroups()
        except KeyError:
            return False

    def get_disk_usage(self) -> int:
        audio_dir = self._data_dir / "audio"
        if not audio_dir.exists():
            return 0
        return sum(f.stat().st_size for f in audio_dir.rglob("*.wav"))
