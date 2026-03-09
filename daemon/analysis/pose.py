"""Pose detection using MediaPipe PoseLandmarker — extracts body keypoints and classifies posture."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# Default model path (downloaded to data/)
_DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "data" / "pose_landmarker_lite.task"


@dataclass
class PoseResult:
    """Result of pose detection on a single frame."""

    detected: bool = False
    posture: str = ""  # sitting, standing, leaning, lying, unknown
    head_tilt: float = 0.0  # degrees from vertical (0 = upright)
    shoulder_angle: float = 0.0  # shoulder line angle (0 = level)
    hands_raised: bool = False
    hands_at_desk: bool = False  # both wrists near or below shoulder height
    confidence: float = 0.0

    def to_json(self) -> str:
        return json.dumps(
            {
                "detected": self.detected,
                "posture": self.posture,
                "head_tilt": round(self.head_tilt, 1),
                "shoulder_angle": round(self.shoulder_angle, 1),
                "hands_raised": self.hands_raised,
                "hands_at_desk": self.hands_at_desk,
                "confidence": round(self.confidence, 2),
            },
            ensure_ascii=False,
        )

    @staticmethod
    def from_json(s: str) -> PoseResult:
        if not s:
            return PoseResult()
        try:
            d = json.loads(s)
            return PoseResult(**d)
        except (json.JSONDecodeError, TypeError):
            return PoseResult()

    def to_prompt_hint(self) -> str:
        """Generate a concise text hint for LLM prompt injection."""
        if not self.detected:
            return ""
        parts = [f"姿勢: {self.posture}"]
        if self.hands_at_desk:
            parts.append("両手デスク付近")
        elif self.hands_raised:
            parts.append("手を上げている")
        if abs(self.head_tilt) > 15:
            direction = "右" if self.head_tilt > 0 else "左"
            parts.append(f"頭部{direction}に傾き({abs(self.head_tilt):.0f}°)")
        if abs(self.shoulder_angle) > 10:
            parts.append(f"肩の傾き({self.shoulder_angle:.0f}°)")
        parts.append(f"信頼度{self.confidence:.0%}")
        return "、".join(parts)


# Skeleton connections for overlay drawing (pairs of landmark indices)
_SKELETON_CONNECTIONS = [
    # Torso
    (11, 12),
    (11, 23),
    (12, 24),
    (23, 24),
    # Left arm
    (11, 13),
    (13, 15),
    # Right arm
    (12, 14),
    (14, 16),
    # Left leg
    (23, 25),
    (25, 27),
    # Right leg
    (24, 26),
    (26, 28),
    # Neck (nose to shoulders)
    (0, 11),
    (0, 12),
]

# Colors (BGR) for different body regions
_COLOR_TORSO = (200, 180, 0)  # teal
_COLOR_ARM = (0, 200, 100)  # green
_COLOR_LEG = (200, 100, 0)  # blue
_COLOR_NECK = (0, 180, 220)  # yellow
_COLOR_JOINT = (0, 160, 255)  # orange circles
_COLOR_LABEL_BG = (30, 30, 30)  # dark background
_COLOR_LABEL_FG = (220, 220, 220)  # light text

_CONN_COLORS = {
    (11, 12): _COLOR_TORSO,
    (11, 23): _COLOR_TORSO,
    (12, 24): _COLOR_TORSO,
    (23, 24): _COLOR_TORSO,
    (11, 13): _COLOR_ARM,
    (13, 15): _COLOR_ARM,
    (12, 14): _COLOR_ARM,
    (14, 16): _COLOR_ARM,
    (23, 25): _COLOR_LEG,
    (25, 27): _COLOR_LEG,
    (24, 26): _COLOR_LEG,
    (26, 28): _COLOR_LEG,
    (0, 11): _COLOR_NECK,
    (0, 12): _COLOR_NECK,
}

# Visibility threshold for drawing
_VIS_THRESH = 0.3


class PoseDetector:
    """Detects body pose using MediaPipe PoseLandmarker (lazy-loaded)."""

    def __init__(self, model_path: Path | None = None):
        self._model_path = model_path or _DEFAULT_MODEL
        self._landmarker = None
        self._available: bool | None = None
        # Cache for overlay drawing
        self._cached_points: list[tuple[int, int, float]] | None = None
        self._cached_result: PoseResult = PoseResult()

    def _ensure_loaded(self) -> bool:
        """Lazy-load MediaPipe PoseLandmarker. Returns True if available."""
        if self._available is not None:
            return self._available
        try:
            import mediapipe as mp

            if not self._model_path.exists():
                log.warning("Pose model not found at %s — pose detection disabled", self._model_path)
                self._available = False
                return False

            base_options = mp.tasks.BaseOptions(
                model_asset_path=str(self._model_path),
            )
            options = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=base_options,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
            )
            self._landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)
            self._available = True
            log.info("MediaPipe PoseLandmarker loaded successfully")
        except ImportError:
            log.warning("mediapipe not installed — pose detection disabled")
            self._available = False
        except Exception:
            log.exception("Failed to initialize MediaPipe PoseLandmarker")
            self._available = False
        return self._available

    def detect(self, frame: np.ndarray) -> PoseResult:
        """Detect pose in a BGR frame. Returns PoseResult."""
        if not self._ensure_loaded():
            return PoseResult()

        import cv2
        import mediapipe as mp

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        try:
            results = self._landmarker.detect(mp_image)
        except Exception:
            log.debug("Pose detection failed on frame", exc_info=True)
            return PoseResult()

        if not results.pose_landmarks or len(results.pose_landmarks) == 0:
            self._cached_points = None
            self._cached_result = PoseResult(detected=False)
            return self._cached_result

        landmarks = results.pose_landmarks[0]  # first person
        h, w = frame.shape[:2]

        # Cache pixel-space points for overlay drawing
        self._cached_points = [(int(lm_pt.x * w), int(lm_pt.y * h), lm_pt.visibility) for lm_pt in landmarks]

        PL = mp.tasks.vision.PoseLandmark

        def lm(idx: int):
            """Get (x, y, visibility) for a landmark index."""
            pt = landmarks[idx]
            return pt.x * w, pt.y * h, pt.visibility

        # Extract key points
        nose_x, nose_y, nose_v = lm(PL.NOSE)
        ls_x, ls_y, ls_v = lm(PL.LEFT_SHOULDER)
        rs_x, rs_y, rs_v = lm(PL.RIGHT_SHOULDER)
        _, _, _ = lm(PL.LEFT_ELBOW)
        _, _, _ = lm(PL.RIGHT_ELBOW)
        lw_x, lw_y, _ = lm(PL.LEFT_WRIST)
        rw_x, rw_y, _ = lm(PL.RIGHT_WRIST)
        lh_x, lh_y, lh_v = lm(PL.LEFT_HIP)
        rh_x, rh_y, rh_v = lm(PL.RIGHT_HIP)

        hip_visible = (lh_v + rh_v) / 2 > 0.3  # hips actually visible in frame

        # Average confidence of key landmarks
        confidence = float(np.mean([nose_v, ls_v, rs_v, lh_v, rh_v]))

        # Shoulder midpoint and angle (deviation from horizontal, 0 = level)
        shoulder_mid_y = (ls_y + rs_y) / 2
        raw_angle = float(np.degrees(np.arctan2(rs_y - ls_y, rs_x - ls_x)))
        # Normalize: 0° means perfectly level shoulders
        shoulder_angle = raw_angle if abs(raw_angle) <= 90 else raw_angle - np.sign(raw_angle) * 180

        # Hip midpoint
        hip_mid_y = (lh_y + rh_y) / 2

        # Head tilt: angle of nose relative to shoulder midpoint
        shoulder_mid_x = (ls_x + rs_x) / 2
        head_tilt = float(np.degrees(np.arctan2(nose_x - shoulder_mid_x, shoulder_mid_y - nose_y)))

        # Hands position
        hands_raised = (lw_y < shoulder_mid_y - 30) and (rw_y < shoulder_mid_y - 30)
        hands_at_desk = (lw_y > shoulder_mid_y - 20) and (rw_y > shoulder_mid_y - 20)

        # Posture classification
        torso_length = abs(hip_mid_y - shoulder_mid_y)
        torso_ratio = torso_length / h if h > 0 else 0

        if not hip_visible:
            # Hips not visible (typical webcam at desk) — infer from upper body only
            posture = "leaning" if abs(head_tilt) > 20 else "sitting"
        elif torso_ratio < 0.08:
            posture = "lying" if shoulder_mid_y > h * 0.5 else "unknown"
        elif torso_ratio < 0.25:
            posture = "leaning" if abs(head_tilt) > 20 else "sitting"
        else:
            posture = "standing"

        self._cached_result = PoseResult(
            detected=True,
            posture=posture,
            head_tilt=head_tilt,
            shoulder_angle=shoulder_angle,
            hands_raised=hands_raised,
            hands_at_desk=hands_at_desk,
            confidence=confidence,
        )
        return self._cached_result

    def draw_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw cached pose skeleton and info on a frame copy. Returns new frame."""
        import cv2

        out = frame.copy()
        points = self._cached_points
        result = self._cached_result

        if points is None or not result.detected:
            return out

        h, w = out.shape[:2]

        # Draw skeleton lines
        for i, j in _SKELETON_CONNECTIONS:
            if i >= len(points) or j >= len(points):
                continue
            px, py, pv = points[i]
            qx, qy, qv = points[j]
            if pv > _VIS_THRESH and qv > _VIS_THRESH:
                color = _CONN_COLORS.get((i, j), _COLOR_TORSO)
                cv2.line(out, (px, py), (qx, qy), color, 2, cv2.LINE_AA)

        # Draw keypoints
        for x, y, v in points:
            if v > _VIS_THRESH:
                cv2.circle(out, (x, y), 4, _COLOR_JOINT, -1, cv2.LINE_AA)
                cv2.circle(out, (x, y), 4, (0, 0, 0), 1, cv2.LINE_AA)

        # Draw info label at bottom
        label = f"{result.posture}  {result.confidence:.0%}"
        if abs(result.head_tilt) > 15:
            label += f"  tilt:{result.head_tilt:.0f}deg"

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        pad = 6
        # Semi-transparent background
        overlay = out.copy()
        cv2.rectangle(overlay, (0, h - th - pad * 2 - baseline), (tw + pad * 2, h), _COLOR_LABEL_BG, -1)
        cv2.addWeighted(overlay, 0.7, out, 0.3, 0, out)
        cv2.putText(out, label, (pad, h - pad - baseline), font, font_scale, _COLOR_LABEL_FG, thickness, cv2.LINE_AA)

        return out
