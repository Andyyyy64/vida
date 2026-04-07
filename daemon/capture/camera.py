from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from daemon.config import CaptureConfig

log = logging.getLogger(__name__)


class Camera:
    def __init__(self, config: CaptureConfig):
        self._config = config
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> bool:
        if sys.platform == "darwin":
            self._cap = cv2.VideoCapture(self._config.device, cv2.CAP_AVFOUNDATION)
        elif sys.platform == "win32":
            # Windows: try multiple backends — DSHOW, MSMF, then default
            for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
                self._cap = cv2.VideoCapture(self._config.device, backend)
                if self._cap.isOpened():
                    break
                self._cap.release()
        else:
            # Linux/WSL2: V4L2 + MJPEG (required for USB cameras via usbipd)
            self._cap = cv2.VideoCapture(self._config.device, cv2.CAP_V4L2)

        if not self._cap.isOpened():
            log.error("Failed to open camera device %d", self._config.device)
            return False

        if sys.platform == "linux":
            # MJPEG format required for WSL2 + USB cameras
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.height)
        self._cap.set(cv2.CAP_PROP_FPS, 30)
        # Minimize internal buffer to reduce latency
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        log.info("Camera opened: device=%d, %dx%d", self._config.device, self._config.width, self._config.height)
        return True

    def capture(self) -> np.ndarray | None:
        if self._cap is None or not self._cap.isOpened():
            log.warning("Camera not opened")
            return None
        ret, frame = self._cap.read()
        if not ret:
            log.warning("Failed to read frame")
            return None
        return frame

    def grab(self) -> bool:
        """Grab a frame without decoding (drains buffer)."""
        if self._cap is None or not self._cap.isOpened():
            return False
        return self._cap.grab()

    def close(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            log.info("Camera closed")

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()
