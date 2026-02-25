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

from life.analysis.motion import MotionDetector
from life.analysis.scene import SceneAnalyzer
from life.analysis.transcribe import Transcriber
from life.analyzer import FrameAnalyzer, SummaryGenerator
from life.capture.audio import AudioCapture
from life.capture.camera import Camera
from life.capture.frame_store import FrameStore
from life.capture.screen import ScreenCapture
from life.config import Config
from life.live import LiveServer
from life.llm import create_provider
from life.storage.database import Database
from life.storage.models import Event, Frame, SceneType, SCALES

log = logging.getLogger(__name__)


class Daemon:
    def __init__(self, config: Config):
        self._config = config
        self._running = False
        self._camera = Camera(config.capture)
        self._frame_store = FrameStore(config.data_dir, config.capture.jpeg_quality)
        self._screen = ScreenCapture(config.data_dir)
        self._audio = AudioCapture(config.data_dir)
        self._db = Database(config.db_path)
        self._motion = MotionDetector(config.analysis.motion_threshold)
        self._scene = SceneAnalyzer(config.analysis.brightness_dark, config.analysis.brightness_bright)
        self._live = LiveServer(port=3002)
        self._frame_count = 0
        self._last_scene: SceneType | None = None
        self._pending_audio: str | None = None  # audio from previous interval
        self._audio_thread: threading.Thread | None = None
        self._burst_screen_paths: list[str] = []  # buffered burst screen captures
        self._burst_lock = threading.Lock()

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

        # Track last summary time per scale
        self._last_summary: dict[str, datetime] = {}

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
        log.info("Daemon started (interval=%ds)", self._config.capture.interval_sec)

        try:
            while self._running:
                self._tick()
                # Between ticks: continuously feed live stream (~10fps)
                # Also capture burst screenshots at 10s intervals
                end_time = time.time() + self._config.capture.interval_sec
                next_burst_time = time.time() + 10  # first burst at +10s
                burst_count = self._config.capture.screen_burst_count
                with self._burst_lock:
                    self._burst_screen_paths = []
                burst_captured = 0
                while self._running and time.time() < end_time:
                    # Burst screen capture at 10s intervals
                    if burst_captured < burst_count - 1 and time.time() >= next_burst_time:
                        self._capture_burst_screen()
                        burst_captured += 1
                        next_burst_time = time.time() + 10
                    raw = self._camera.capture()
                    if raw is not None:
                        _, jpeg = cv2.imencode(
                            ".jpg", raw, [cv2.IMWRITE_JPEG_QUALITY, 70]
                        )
                        self._live.update_frame(jpeg.tobytes())
                    time.sleep(0.1)
        except Exception:
            log.exception("Daemon crashed")
        finally:
            self._live.stop()
            self._camera.close()
            self._db.close()
            self._cleanup_pid()
            log.info("Daemon stopped")

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

    def _capture_burst_screen(self):
        """Capture a burst screenshot in background thread."""
        def _do_capture():
            path = self._screen.capture(datetime.now())
            if path:
                with self._burst_lock:
                    self._burst_screen_paths.append(path)
                log.debug("Burst screen captured: %s", path)
        t = threading.Thread(target=_do_capture, daemon=True)
        t.start()

    def _tick(self):
        raw_frame = self._camera.capture()
        if raw_frame is None:
            return

        # Update live feed
        _, jpeg = cv2.imencode(".jpg", raw_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        self._live.update_frame(jpeg.tobytes())

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

        # Collect burst screen paths from previous interval
        with self._burst_lock:
            burst_paths = list(self._burst_screen_paths)
            self._burst_screen_paths = []

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
            screen_extra_paths=",".join(burst_paths) if burst_paths else "",
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
            "frame=%d bright=%.0f motion=%.3f scene=%s audio=%s",
            self._frame_count, brightness, motion_score, scene_type.value,
            "yes" if audio_path else "no",
        )

        # LLM frame analysis (every frame, with transcription context + burst screens)
        description, activity = self._frame_analyzer.analyze(frame, burst_paths or None)
        if description or activity:
            self._db.update_frame_analysis(frame_id, description, activity)
            log.info("Analysis: [%s] %s", activity, description[:80])

        # Multi-scale summaries
        self._check_summaries(now)

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

    def _write_pid(self):
        self._config.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self._config.pid_file.write_text(str(os.getpid()))

    def _cleanup_pid(self):
        if self._config.pid_file.exists():
            self._config.pid_file.unlink()

    def _handle_signal(self, signum, _frame):
        log.info("Received signal %d, stopping...", signum)
        self._running = False
