"""Presence detection — face detection + state machine for idle/sleep mode."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum

import cv2
import numpy as np

log = logging.getLogger(__name__)


class PresenceState(Enum):
    PRESENT = "present"
    ABSENT = "absent"
    SLEEPING = "sleeping"


class PresenceDetector:
    """Detects user presence via face detection and motion, with hysteresis."""

    def __init__(
        self,
        absent_threshold_ticks: int = 3,
        sleep_start_hour: int = 23,
        sleep_end_hour: int = 8,
    ):
        self._absent_threshold = absent_threshold_ticks
        self._sleep_start = sleep_start_hour
        self._sleep_end = sleep_end_hour
        self._state = PresenceState.PRESENT
        self._absent_ticks = 0

        # Load Haar cascade for face detection
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"
        self._face_cascade = cv2.CascadeClassifier(cascade_path)
        if self._face_cascade.empty():
            log.warning("Failed to load Haar cascade from %s", cascade_path)

    @property
    def state(self) -> PresenceState:
        return self._state

    @property
    def is_idle(self) -> bool:
        return self._state in (PresenceState.ABSENT, PresenceState.SLEEPING)

    def detect_face(self, frame: np.ndarray) -> bool:
        """Detect whether a face is present in the frame."""
        if self._face_cascade.empty():
            return False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cv2.equalizeHist(gray, gray)
        faces = self._face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.3,
            minNeighbors=3,
            minSize=(60, 60),
        )
        return len(faces) > 0

    def _is_sleep_window(self, now: datetime) -> bool:
        """Check if current time is in the sleep window."""
        hour = now.hour
        if self._sleep_start > self._sleep_end:
            # Wraps midnight: e.g. 23:00 - 08:00
            return hour >= self._sleep_start or hour < self._sleep_end
        else:
            return self._sleep_start <= hour < self._sleep_end

    def update(
        self,
        brightness: float,
        motion_score: float,
        has_face: bool,
        now: datetime,
    ) -> PresenceState:
        """Update presence state machine. Returns new state."""
        prev_state = self._state

        if has_face or motion_score > 0.05:
            # Instant recovery to present
            self._absent_ticks = 0
            self._state = PresenceState.PRESENT
        else:
            # No face, no significant motion
            self._absent_ticks += 1
            if self._absent_ticks >= self._absent_threshold:
                if self._is_sleep_window(now) and brightness < 60:
                    self._state = PresenceState.SLEEPING
                else:
                    self._state = PresenceState.ABSENT

        if self._state != prev_state:
            log.info(
                "Presence: %s -> %s (ticks=%d, bright=%.0f, motion=%.3f, face=%s)",
                prev_state.value,
                self._state.value,
                self._absent_ticks,
                brightness,
                motion_score,
                has_face,
            )

        return self._state
