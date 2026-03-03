"""Enumerate available camera and audio input devices. Outputs JSON to stdout.

Run as: python daemon/devices.py
"""
from __future__ import annotations

import glob
import json
import re
import subprocess
import sys


# ── Camera ────────────────────────────────────────────────────────────────────

def _cameras_linux() -> list[dict]:
    devices = []
    for path in sorted(glob.glob("/dev/video*")):
        try:
            idx = int(path.replace("/dev/video", ""))
        except ValueError:
            continue
        # Read human-friendly name from sysfs
        try:
            name_path = f"/sys/class/video4linux/video{idx}/name"
            with open(name_path) as f:
                name = f.read().strip()
        except OSError:
            name = f"Camera {idx}"
        devices.append({"index": idx, "name": f"{name} (/dev/video{idx})"})
    return devices


def _cameras_mac() -> list[dict]:
    try:
        result = subprocess.run(
            ["system_profiler", "SPCameraDataType"],
            capture_output=True, text=True, timeout=5,
        )
        devices = []
        idx = 0
        for line in result.stdout.splitlines():
            line = line.strip()
            # Lines like "FaceTime HD Camera:"
            if line.endswith(":") and line not in ("Camera:", "SPCameraDataType:"):
                name = line.rstrip(":")
                devices.append({"index": idx, "name": name})
                idx += 1
        if devices:
            return devices
    except Exception:
        pass
    # Fallback: probe cv2
    return _cameras_cv2(cv2_backend_flag("darwin"))


def _cameras_windows() -> list[dict]:
    # Try PowerShell first for friendly names
    try:
        ps_cmd = (
            "Get-PnpDevice -Class Camera -Status OK | "
            "Select-Object -ExpandProperty FriendlyName"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=8,
        )
        names = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        if names:
            return [{"index": i, "name": n} for i, n in enumerate(names)]
    except Exception:
        pass
    return _cameras_cv2(cv2_backend_flag("win32"))


def cv2_backend_flag(platform: str) -> int:
    try:
        import cv2
        return {
            "darwin": cv2.CAP_AVFOUNDATION,
            "win32": cv2.CAP_DSHOW,
        }.get(platform, cv2.CAP_ANY)
    except ImportError:
        return 0


def _cameras_cv2(backend: int) -> list[dict]:
    """Probe camera indices 0–6 via OpenCV."""
    try:
        import cv2
    except ImportError:
        return []
    devices = []
    for i in range(7):
        cap = cv2.VideoCapture(i, backend)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            if ret:
                devices.append({"index": i, "name": f"Camera {i}"})
        elif i > 0 and not devices:
            # No device found at index 0 either, stop early
            break
        cap.release()
    return devices


def list_cameras() -> list[dict]:
    if sys.platform == "linux":
        return _cameras_linux()
    elif sys.platform == "darwin":
        return _cameras_mac()
    elif sys.platform == "win32":
        return _cameras_windows()
    return _cameras_cv2(0)


# ── Audio ─────────────────────────────────────────────────────────────────────

def _audio_linux() -> list[dict]:
    """Enumerate ALSA capture devices via arecord -l."""
    try:
        result = subprocess.run(
            ["arecord", "-l"], capture_output=True, text=True, timeout=5,
        )
        devices = [{"id": "", "name": "Auto-detect (default)"}]
        for line in result.stdout.splitlines():
            m = re.match(r"card (\d+):.*\[(.+?)\].*device (\d+):", line)
            if m:
                card, name, dev = int(m.group(1)), m.group(2), int(m.group(3))
                alsa_id = f"plughw:{card},{dev}"
                devices.append({"id": alsa_id, "name": f"{name} ({alsa_id})"})
        return devices
    except FileNotFoundError:
        return [{"id": "", "name": "arecord not found — install alsa-utils"}]
    except Exception:
        return [{"id": "", "name": "Auto-detect (default)"}]


def _audio_sounddevice() -> list[dict]:
    """Enumerate audio input devices via sounddevice (Mac / Windows)."""
    try:
        import sounddevice as sd
        all_devs = sd.query_devices()
        devices = [{"id": "", "name": "System default"}]
        for dev in all_devs:
            if dev["max_input_channels"] > 0:
                devices.append({"id": dev["name"], "name": dev["name"]})
        return devices
    except ImportError:
        return [{"id": "", "name": "sounddevice not installed"}]
    except Exception:
        return [{"id": "", "name": "System default"}]


def list_audio() -> list[dict]:
    if sys.platform == "linux":
        return _audio_linux()
    return _audio_sounddevice()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(json.dumps({"cameras": list_cameras(), "audio": list_audio()}))
