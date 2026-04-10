from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

# PowerShell script: save to Windows temp file, output the path
_PS_SCRIPT_TEMP = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$tmpFile = [System.IO.Path]::GetTempFileName() -replace '\.tmp$','.png'
$bitmap.Save($tmpFile)
$graphics.Dispose()
$bitmap.Dispose()
Write-Output $tmpFile
"""

# PowerShell script for native Windows. The target path is read from the
# $env:VIDA_SCREEN_PATH environment variable (NOT interpolated into the
# script body) so that paths containing quotes or PowerShell metacharacters
# can never be misinterpreted as code.
_PS_SCRIPT_DIRECT = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$target = $env:VIDA_SCREEN_PATH
if (-not $target) { throw 'VIDA_SCREEN_PATH not set' }
$bitmap.Save($target)
$graphics.Dispose()
$bitmap.Dispose()
"""


class ScreenCapture:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir

    def capture(self, timestamp: datetime | None = None) -> str | None:
        """Capture the screen and save as PNG. Returns relative path or None."""
        timestamp = timestamp or datetime.now()
        date_dir = self._data_dir / "screens" / timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        filename = timestamp.strftime("%H-%M-%S") + ".png"
        filepath = date_dir / filename

        if sys.platform == "darwin":
            return self._capture_mac(filepath)
        elif sys.platform == "win32":
            return self._capture_windows(filepath)
        else:
            return self._capture_wsl(filepath)

    def _capture_mac(self, filepath: Path) -> str | None:
        """Capture screen using macOS built-in screencapture command."""
        try:
            result = subprocess.run(
                ["screencapture", "-x", "-t", "png", str(filepath)],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                log.warning("screencapture failed: %s", result.stderr[:200])
                return None
            if not filepath.exists():
                log.warning("Screenshot file not created: %s", filepath)
                return None
            rel_path = str(filepath.relative_to(self._data_dir))
            log.debug("Screen captured (mac): %s", rel_path)
            return rel_path
        except subprocess.TimeoutExpired:
            log.warning("screencapture timed out")
            return None
        except FileNotFoundError:
            log.warning("screencapture not found (not running on macOS?)")
            return None
        except Exception:
            log.exception("Screen capture error")
            return None

    def _capture_windows(self, filepath: Path) -> str | None:
        """Capture screen on native Windows using PowerShell directly.

        The target path is passed via environment variable so that paths
        containing quotes/metacharacters can't be interpreted as PowerShell
        code (command injection defence).
        """
        env = os.environ.copy()
        env["VIDA_SCREEN_PATH"] = str(filepath)
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_SCRIPT_DIRECT],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=env,
            )
            if result.returncode != 0:
                log.warning("Screen capture failed: %s", result.stderr[:200])
                return None
            if not filepath.exists():
                log.warning("Screenshot file not created: %s", filepath)
                return None
            rel_path = str(filepath.relative_to(self._data_dir))
            log.debug("Screen captured (windows): %s", rel_path)
            return rel_path
        except subprocess.TimeoutExpired:
            log.warning("Screen capture timed out")
            return None
        except FileNotFoundError:
            log.warning("powershell not found")
            return None
        except Exception:
            log.exception("Screen capture error")
            return None

    def _capture_wsl(self, filepath: Path) -> str | None:
        """Capture Windows screen from WSL2 via PowerShell temp file."""
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", _PS_SCRIPT_TEMP],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if result.returncode != 0:
                log.warning("Screen capture failed: %s", result.stderr[:200])
                return None
            win_tmp = result.stdout.strip()
            if not win_tmp:
                log.warning("Screen capture returned no temp path")
                return None
            # Convert Windows path to WSL path and copy
            wsl_tmp = subprocess.run(
                ["wslpath", win_tmp],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
            if not wsl_tmp or not Path(wsl_tmp).exists():
                log.warning("Temp screenshot not found: %s", wsl_tmp)
                return None
            shutil.move(wsl_tmp, filepath)
            rel_path = str(filepath.relative_to(self._data_dir))
            log.debug("Screen captured (wsl): %s", rel_path)
            return rel_path
        except subprocess.TimeoutExpired:
            log.warning("Screen capture timed out")
            return None
        except FileNotFoundError:
            log.warning("powershell.exe not found (not running in WSL2?)")
            return None
        except Exception:
            log.exception("Screen capture error")
            return None

    def get_disk_usage(self) -> int:
        screens_dir = self._data_dir / "screens"
        if not screens_dir.exists():
            return 0
        return sum(f.stat().st_size for f in screens_dir.rglob("*.png"))
