from __future__ import annotations

import cv2
import numpy as np

from life_ai.storage.models import SceneType


class SceneAnalyzer:
    def __init__(self, dark_threshold: float = 40.0, bright_threshold: float = 180.0):
        self._dark = dark_threshold
        self._bright = bright_threshold

    def get_brightness(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray))

    def classify(self, brightness: float) -> SceneType:
        if brightness < self._dark:
            return SceneType.DARK
        elif brightness > self._bright:
            return SceneType.BRIGHT
        return SceneType.NORMAL
