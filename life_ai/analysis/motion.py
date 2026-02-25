from __future__ import annotations

import cv2
import numpy as np


class MotionDetector:
    def __init__(self, threshold: float = 0.02):
        self._threshold = threshold
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=50, detectShadows=False
        )

    def analyze(self, frame: np.ndarray) -> float:
        """Return motion score (0.0 - 1.0) based on foreground pixel ratio."""
        fg_mask = self._bg_subtractor.apply(frame)
        # Remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        motion_ratio = np.count_nonzero(fg_mask) / fg_mask.size
        return float(motion_ratio)

    def has_motion(self, score: float) -> bool:
        return score > self._threshold

    def reset(self):
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=50, detectShadows=False
        )
