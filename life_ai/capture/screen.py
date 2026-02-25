from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

# PowerShell script template for Windows screen capture from WSL2
_PS_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bitmap.Save('{path}')
$graphics.Dispose()
$bitmap.Dispose()
"""


def _wsl_to_unc(posix_path: str) -> str:
    """Convert WSL2 absolute path to UNC path for Windows access."""
    return r"\\wsl.localhost\Ubuntu" + posix_path


class ScreenCapture:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir

    def capture(self, timestamp: datetime | None = None) -> str | None:
        """Capture the Windows screen and save as PNG. Returns relative path or None."""
        timestamp = timestamp or datetime.now()
        date_dir = self._data_dir / "screens" / timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        filename = timestamp.strftime("%H-%M-%S") + ".png"
        filepath = date_dir / filename
        unc_path = _wsl_to_unc(str(filepath.resolve()))

        script = _PS_SCRIPT.format(path=unc_path)
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                log.warning("Screen capture failed: %s", result.stderr[:200])
                return None
            if not filepath.exists():
                log.warning("Screenshot file not created: %s", filepath)
                return None
            rel_path = str(filepath.relative_to(self._data_dir))
            log.debug("Screen captured: %s", rel_path)
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
