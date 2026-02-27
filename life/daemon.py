from __future__ import annotations

import logging
import os
import shutil
import signal
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import cv2

from life.analysis.change import ChangeDetector
from life.analysis.motion import MotionDetector
from life.analysis.presence import PresenceDetector
from life.analysis.scene import SceneAnalyzer
from life.analysis.transcribe import Transcriber
from life.analyzer import FrameAnalyzer, SummaryGenerator
from life.report import ReportGenerator
from life.capture.audio import AudioCapture
from life.capture.camera import Camera
from life.capture.frame_store import FrameStore
from life.capture.screen import ScreenCapture
from life.config import Config
from life.live import LiveServer
from life.llm import create_provider
from life.notify import send_notification
from life.storage.database import Database
from life.storage.models import Event, Frame, SceneType, SCALES

CHANGE_CHECK_INTERVAL = 1  # seconds between change checks

log = logging.getLogger(__name__)


class Daemon:
    def __init__(self, config: Config):
        self._config = config
        self._running = False
        self._camera = Camera(config.capture)
        self._frame_store = FrameStore(config.data_dir, config.capture.jpeg_quality)
        self._screen = ScreenCapture(config.data_dir)
        self._audio = AudioCapture(config.data_dir, config.capture.audio_device, config.capture.audio_sample_rate)
        self._db = Database(config.db_path)
        self._motion = MotionDetector(config.analysis.motion_threshold)
        self._scene = SceneAnalyzer(config.analysis.brightness_dark, config.analysis.brightness_bright)
        self._live = LiveServer(port=3002)
        self._cam_lock = threading.Lock()  # protect cv2.VideoCapture across threads
        self._frame_count = 0
        self._last_scene: SceneType | None = None
        self._pending_audio: str | None = None  # audio from previous interval
        self._audio_thread: threading.Thread | None = None
        # Change-detection based capture buffers
        self._screen_detector = ChangeDetector(threshold=0.10)
        self._cam_detector = ChangeDetector(threshold=0.15)
        self._extra_screen_paths: list[str] = []
        self._extra_cam_paths: list[str] = []
        self._capture_lock = threading.Lock()

        # Presence detection
        self._presence = PresenceDetector(
            absent_threshold_ticks=config.presence.absent_threshold_ticks,
            sleep_start_hour=config.presence.sleep_start_hour,
            sleep_end_hour=config.presence.sleep_end_hour,
        )
        self._presence_enabled = config.presence.enabled

        # Create LLM provider from config
        provider = create_provider(
            config.llm.provider,
            claude_model=config.llm.claude_model,
            gemini_model=config.llm.gemini_model,
        )
        log.info("LLM provider: %s", config.llm.provider)

        self._transcriber = Transcriber(
            provider, context_path=config.data_dir / "context.md",
        )
        self._frame_analyzer = FrameAnalyzer(provider, config.data_dir, self._db)
        self._summary_gen = SummaryGenerator(provider, self._db, config.data_dir)
        self._report_gen = ReportGenerator(provider, self._db, config.data_dir)

        # Track last summary time per scale
        # Initialize to now so we wait the full interval before first generation
        now = datetime.now()
        self._last_summary: dict[str, datetime] = {scale: now for scale in SCALES}
        self._last_report_date: str = now.strftime("%Y-%m-%d")

    def run(self):
        self._write_pid()
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        if not self._camera.open():
            log.error("Cannot start: camera failed to open")
            self._cleanup_pid()
            return

        self._running = True
        self._live.start()
        self._start_live_thread()
        log.info("Daemon started (interval=%ds)", self._config.capture.interval_sec)

        try:
            while self._running:
                self._tick()
                # Between ticks: check for screen and camera changes every second
                end_time = time.time() + self._config.capture.interval_sec
                next_check = time.time() + CHANGE_CHECK_INTERVAL
                with self._capture_lock:
                    self._extra_screen_paths = []
                    self._extra_cam_paths = []
                self._screen_detector.reset()
                self._cam_detector.reset()
                while self._running and time.time() < end_time:
                    now_t = time.time()
                    if now_t >= next_check:
                        self._check_screen_change()
                        self._check_cam_change()
                        next_check = now_t + CHANGE_CHECK_INTERVAL
                    time.sleep(0.2)
        except Exception:
            log.exception("Daemon crashed")
        finally:
            self._running = False
            self._live.stop()
            self._camera.close()
            self._db.close()
            self._cleanup_pid()
            log.info("Daemon stopped")

    def _start_live_thread(self) -> None:
        """Run dedicated thread that feeds camera frames to the live server at ~30fps."""
        def _feed():
            while self._running:
                with self._cam_lock:
                    raw = self._camera.capture()
                if raw is not None:
                    _, jpeg = cv2.imencode(
                        ".jpg", raw, [cv2.IMWRITE_JPEG_QUALITY, 70]
                    )
                    self._live.update_frame(jpeg.tobytes())
                time.sleep(0.033)  # ~30fps
        thread = threading.Thread(target=_feed, daemon=True, name="live-feed")
        thread.start()

    def _start_audio_recording(self, now: datetime):
        """Start recording audio in a background thread for the current interval."""
        def _record():
            self._pending_audio = self._audio.capture(
                duration_sec=self._config.capture.interval_sec, timestamp=now
            )
        self._audio_thread = threading.Thread(target=_record, daemon=True)
        self._audio_thread.start()

    def _collect_audio(self) -> tuple[str, str]:
        """Collect audio from previous interval: returns (audio_path, transcription)."""
        if self._audio_thread is not None:
            self._audio_thread.join(timeout=5)
            self._audio_thread = None

        audio_path = self._pending_audio or ""
        self._pending_audio = None
        transcription = ""
        if audio_path:
            abs_audio = self._config.data_dir / audio_path
            transcription = self._transcriber.transcribe(Path(abs_audio))
            if transcription:
                log.info("Transcribed: %s", transcription[:80])
        return audio_path, transcription

    def _check_screen_change(self) -> None:
        """Capture a screenshot and keep it only if the screen changed."""
        def _do_check():
            path = self._screen.capture(datetime.now())
            if not path:
                return
            abs_path = self._config.data_dir / path
            if self._screen_detector.is_changed_file(abs_path):
                with self._capture_lock:
                    self._extra_screen_paths.append(path)
                    log.debug("Screen change detected (%d): %s",
                              len(self._extra_screen_paths), path)
            else:
                # No change — delete the file
                try:
                    abs_path.unlink()
                except OSError:
                    pass

        threading.Thread(target=_do_check, daemon=True).start()

    def _check_cam_change(self) -> None:
        """Capture a camera frame and keep it only if the view changed."""
        with self._cam_lock:
            raw = self._camera.capture()
        if raw is None:
            return

        if self._cam_detector.is_changed(raw):
            now = datetime.now()
            rel_path = self._frame_store.save(raw, now)
            with self._capture_lock:
                self._extra_cam_paths.append(rel_path)
                log.debug("Camera change detected (%d): %s",
                          len(self._extra_cam_paths), rel_path)

    def _tick(self):
        with self._cam_lock:
            raw_frame = self._camera.capture()
        if raw_frame is None:
            return

        now = datetime.now()
        self._frame_count += 1

        # Collect audio from previous interval (recorded during sleep)
        audio_path, transcription = self._collect_audio()

        # Start recording audio for the next interval (runs during processing + sleep)
        self._start_audio_recording(now)

        # Save webcam frame + screen capture
        rel_path = self._frame_store.save(raw_frame, now)
        screen_path = self._screen.capture(now) or ""

        # Write latest frame for live web feed
        live_dir = self._config.data_dir / "live"
        live_dir.mkdir(exist_ok=True)
        shutil.copy2(str(self._config.data_dir / rel_path), str(live_dir / "latest.jpg"))

        # Local lightweight analysis
        brightness = self._scene.get_brightness(raw_frame)
        scene_type = self._scene.classify(brightness)
        motion_score = self._motion.analyze(raw_frame)

        # Presence detection (used as hint for LLM, not to skip processing)
        has_face: bool | None = None
        if self._presence_enabled:
            has_face = self._presence.detect_face(raw_frame)
            prev_state = self._presence.state
            self._presence.update(brightness, motion_score, has_face, now)
            new_state = self._presence.state

            if new_state != prev_state:
                log.info("Presence: %s -> %s", prev_state.value, new_state.value)
                self._db.insert_event(Event(
                    timestamp=now,
                    event_type="presence_change",
                    description=f"{prev_state.value} → {new_state.value}",
                ))

        # Collect change-detected extra captures from previous interval
        with self._capture_lock:
            extra_screens = list(self._extra_screen_paths)
            extra_cams = list(self._extra_cam_paths)
            self._extra_screen_paths = []
            self._extra_cam_paths = []

        if extra_screens or extra_cams:
            log.info("Change captures: %d screens, %d cams",
                     len(extra_screens), len(extra_cams))

        # Record frame in DB
        frame = Frame(
            timestamp=now,
            path=rel_path,
            screen_path=screen_path,
            audio_path=audio_path,
            transcription=transcription,
            brightness=brightness,
            motion_score=motion_score,
            scene_type=scene_type,
            screen_extra_paths=",".join(extra_screens) if extra_screens else "",
        )
        frame_id = self._db.insert_frame(frame)
        frame.id = frame_id

        # Scene change event
        if self._last_scene and scene_type != self._last_scene:
            self._db.insert_event(Event(
                timestamp=now,
                event_type="scene_change",
                description=f"{self._last_scene.value} → {scene_type.value}",
                frame_id=frame_id,
            ))
        self._last_scene = scene_type

        # Motion spike event
        if motion_score > self._config.analysis.motion_threshold * 5:
            self._db.insert_event(Event(
                timestamp=now,
                event_type="motion_spike",
                description=f"大きな動き検知 (score={motion_score:.3f})",
                frame_id=frame_id,
            ))

        log.info(
            "frame=%d bright=%.0f motion=%.3f scene=%s presence=%s audio=%s",
            self._frame_count, brightness, motion_score, scene_type.value,
            self._presence.state.value if self._presence_enabled else "n/a",
            "yes" if audio_path else "no",
        )

        # LLM frame analysis (with change-detected extra captures + presence hint)
        all_extra_screens = extra_screens or None
        all_extra_cams = extra_cams or None
        description, activity = self._frame_analyzer.analyze(
            frame, all_extra_screens, all_extra_cams, has_face=has_face,
        )
        if description or activity:
            self._db.update_frame_analysis(frame_id, description, activity)
            log.info("Analysis: [%s] %s", activity, description[:80])

        # Multi-scale summaries
        self._check_summaries(now)

        # Auto-generate daily report when day changes
        today_str = now.strftime("%Y-%m-%d")
        if today_str != self._last_report_date:
            yesterday = (now - timedelta(days=1)).date()
            existing = self._db.get_report(yesterday)
            if not existing:
                log.info("Generating daily report for %s...", yesterday)
                report = self._report_gen.generate(yesterday)
                if report:
                    self._send_report_notification(yesterday, report)
            self._last_report_date = today_str

    def _check_summaries(self, now: datetime):
        generators = {
            "10m": self._summary_gen.generate_10m,
            "30m": self._summary_gen.generate_30m,
            "1h": self._summary_gen.generate_1h,
            "6h": self._summary_gen.generate_6h,
            "12h": self._summary_gen.generate_12h,
            "24h": self._summary_gen.generate_24h,
        }

        for scale, interval_sec in SCALES.items():
            last = self._last_summary.get(scale)
            if last and (now - last).total_seconds() < interval_sec:
                continue

            gen_fn = generators[scale]
            log.info("Generating %s summary...", scale)
            summary = gen_fn(now)
            if summary:
                self._last_summary[scale] = now
                log.info("Summary [%s]: %s", scale, summary.content[:80])

    def _send_report_notification(self, report_date, report):
        """Send daily report via configured notification channel."""
        title = f"life.ai Daily Report — {report_date.isoformat()}"
        body = f"{report.content}\n\n{report.frame_count} frames | Focus {report.focus_pct:.0f}%"
        send_notification(self._config.notify, title, body)

    def _write_pid(self):
        self._config.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self._config.pid_file.write_text(str(os.getpid()))

    def _cleanup_pid(self):
        if self._config.pid_file.exists():
            self._config.pid_file.unlink()

    def _handle_signal(self, signum, _frame):
        log.info("Received signal %d, stopping...", signum)
        self._running = False
