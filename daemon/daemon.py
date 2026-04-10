from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import shutil
import signal
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import cv2

from daemon.activity import ActivityManager
from daemon.analysis.change import ChangeDetector
from daemon.analysis.motion import MotionDetector
from daemon.analysis.pose import PoseDetector
from daemon.analysis.presence import PresenceDetector
from daemon.analysis.scene import SceneAnalyzer
from daemon.analysis.transcribe import Transcriber
from daemon.analyzer import FrameAnalyzer, SummaryGenerator
from daemon.capture.audio import AudioCapture
from daemon.capture.camera import Camera
from daemon.capture.frame_store import FrameStore
from daemon.capture.screen import ScreenCapture
from daemon.capture.window import WindowMonitor
from daemon.chat.manager import ChatManager
from daemon.config import Config
from daemon.embedding import Embedder
from daemon.knowledge import KnowledgeGenerator
from daemon.live import LiveServer
from daemon.llm import create_provider
from daemon.notify import send_notification
from daemon.rag_server import RagServer
from daemon.report import ReportGenerator
from daemon.retention import cleanup_old_data
from daemon.storage.database import Database
from daemon.storage.models import SCALES, Event, Frame, SceneType
from daemon.ws_server import WebSocketServer, WSEvent

CHANGE_CHECK_INTERVAL = 1  # seconds between change checks

log = logging.getLogger(__name__)

# Heuristic patterns used to scrub secrets from exception messages before
# broadcasting them to WebSocket clients. LLM SDKs often embed the API key in
# URL query strings or error messages verbatim.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(key=)[^&\s'\"]+", re.IGNORECASE),
    re.compile(r"(api[_-]?key['\"]?\s*[:=]\s*['\"]?)[A-Za-z0-9_\-]{10,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),  # OpenAI-style
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),  # Google API key format
)


def _scrub_secrets(text: str) -> str:
    """Remove API keys / bearer tokens from an arbitrary string."""
    if not text:
        return text
    for pat in _SECRET_PATTERNS:
        text = pat.sub(lambda m: (m.group(1) if m.groups() else "") + "***", text)
    return text


class Daemon:
    def __init__(self, config: Config):
        self._config = config
        self._running = False
        self._camera = Camera(config.capture)
        self._frame_store = FrameStore(config.data_dir, config.capture.jpeg_quality)
        self._screen = ScreenCapture(config.data_dir)
        self._window = WindowMonitor(config.db_path)
        self._audio = AudioCapture(config.data_dir, config.capture.audio_device, config.capture.audio_sample_rate)
        self._db = Database(config.db_path, embedding_dimensions=config.embedding.dimensions)
        self._motion = MotionDetector(config.analysis.motion_threshold)
        self._scene = SceneAnalyzer(config.analysis.brightness_dark, config.analysis.brightness_bright)
        self._pose = PoseDetector()
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
        self._consecutive_cam_failures = 0
        self._cam_reconnect_cooldown: float = 0  # time.time() after which reconnect is allowed

        # Presence detection
        self._presence = PresenceDetector(
            absent_threshold_ticks=config.presence.absent_threshold_ticks,
            sleep_start_hour=config.presence.sleep_start_hour,
            sleep_end_hour=config.presence.sleep_end_hour,
        )
        self._presence_enabled = config.presence.enabled

        # Create LLM provider from config (None in external mode)
        if config.llm.provider == "external":
            provider = None
            log.info("LLM provider: external (Claude Code via WebSocket)")
        else:
            provider = create_provider(
                config.llm.provider,
                claude_model=config.llm.claude_model,
                gemini_model=config.llm.gemini_model,
            )
            log.info("LLM provider: %s", config.llm.provider)

        # Multimodal embedder
        self._embedding_enabled = config.embedding.enabled
        self._embedder = Embedder(model=config.embedding.model, dimensions=config.embedding.dimensions)
        if self._embedding_enabled:
            log.info("Embedding enabled (model=%s, dims=%d)", config.embedding.model, config.embedding.dimensions)

        self._activity_mgr = ActivityManager(self._db)
        if provider:
            self._transcriber = Transcriber(
                provider,
                context_path=config.data_dir / "context.md",
            )
            self._frame_analyzer = FrameAnalyzer(provider, config.data_dir, self._db, self._activity_mgr)
            self._summary_gen = SummaryGenerator(provider, self._db, config.data_dir)
            self._report_gen = ReportGenerator(provider, self._db, config.data_dir, self._activity_mgr)
            self._knowledge_gen = KnowledgeGenerator(provider, self._db, config.data_dir)
        else:
            self._transcriber = None
            self._frame_analyzer = None
            self._summary_gen = None
            self._report_gen = None
            self._knowledge_gen = None
        self._knowledge_interval_days = config.knowledge_interval_days
        self._chat_mgr = ChatManager(config.db_path, config.chat)
        # RAG server requires an LLM provider — skip in external mode
        if config.llm.provider != "external":
            self._rag_server = RagServer(config, port=3003)
        else:
            self._rag_server = None
        self._ws = WebSocketServer(port=3004)
        self._ws.on_message = self._handle_ws_message

        self._consecutive_llm_failures = 0

        # Track last summary time per scale
        # Initialize to now so we wait the full interval before first generation
        now = datetime.now()
        self._last_summary: dict[str, datetime] = {scale: now for scale in SCALES}
        self._last_report_date: str = now.strftime("%Y-%m-%d")
        self._last_cleanup_date: str = ""  # triggers cleanup on first tick

    def run(self):
        try:
            import setproctitle

            setproctitle.setproctitle("vida")
        except ImportError:
            pass
        # Tighten the umask so any new files/dirs created by this process
        # (frames, screens, audio, status.json, pid) are owner-only. Other
        # local users should never be able to read captured media or the
        # SQLite database.
        with contextlib.suppress(Exception):
            os.umask(0o077)
        self._secure_data_dir()
        self._write_pid()
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._has_camera = self._camera.open()
        if not self._has_camera:
            log.warning("Camera not available — running without camera")

        self._has_mic = self._audio.is_available()
        if not self._has_mic:
            log.warning("Microphone not available — running without audio capture")

        self._running = True
        self._live.start()
        if self._rag_server:
            self._rag_server.start()
        self._ws.start()
        self._window.start()
        self._chat_mgr.start()
        if self._has_camera:
            self._start_live_thread()
        self._write_status()
        log.info(
            "Daemon started (interval=%ds, camera=%s)",
            self._config.capture.interval_sec,
            "yes" if self._has_camera else "no",
        )

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
                        if self._has_camera:
                            self._check_cam_change()
                        next_check = now_t + CHANGE_CHECK_INTERVAL
                    time.sleep(0.2)
        except Exception:
            log.exception("Daemon crashed")
        finally:
            self._running = False
            self._chat_mgr.stop()
            self._window.stop()
            self._ws.stop()
            if self._rag_server:
                self._rag_server.stop()
            self._live.stop()
            self._camera.close()
            self._db.close()
            self._cleanup_pid()
            log.info("Daemon stopped")

    def _start_live_thread(self) -> None:
        """Run dedicated thread that feeds camera frames to the live server at ~30fps.

        Runs pose detection every ~10th frame and draws skeleton overlay
        on a separate stream (/stream/pose).
        """

        def _feed():
            live_pose = PoseDetector()  # separate instance for live thread
            frame_n = 0
            pose_interval = 10  # detect every 10th frame (~3fps)

            while self._running:
                with self._cam_lock:
                    raw = self._camera.capture()
                if raw is not None:
                    # Encode original
                    _, jpeg = cv2.imencode(".jpg", raw, [cv2.IMWRITE_JPEG_QUALITY, 70])

                    # Pose overlay (throttled detection, draw every frame)
                    frame_n += 1
                    if frame_n % pose_interval == 0:
                        live_pose.detect(raw)
                    pose_frame = live_pose.draw_overlay(raw)
                    _, jpeg_pose = cv2.imencode(".jpg", pose_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])

                    self._live.update_frame(jpeg.tobytes(), jpeg_pose.tobytes())
                time.sleep(0.033)  # ~30fps

        thread = threading.Thread(target=_feed, daemon=True, name="live-feed")
        thread.start()

    def _start_audio_recording(self, now: datetime):
        """Start recording audio in a background thread for the current interval."""

        def _record():
            self._pending_audio = self._audio.capture(duration_sec=self._config.capture.interval_sec, timestamp=now)

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
        if audio_path and self._transcriber:
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
                    log.debug("Screen change detected (%d): %s", len(self._extra_screen_paths), path)
            else:
                # No change — delete the file
                with contextlib.suppress(OSError):
                    abs_path.unlink()

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
                log.debug("Camera change detected (%d): %s", len(self._extra_cam_paths), rel_path)

    def _try_reconnect_camera(self) -> bool:
        """Close and reopen the camera after consecutive capture failures.

        Returns True if the camera was successfully reconnected.
        """
        if time.time() < self._cam_reconnect_cooldown:
            return False

        log.warning("Attempting camera reconnect after %d consecutive failures", self._consecutive_cam_failures)
        with self._cam_lock:
            self._camera.close()
            success = self._camera.open()

        if success:
            log.info("Camera reconnected successfully")
            self._consecutive_cam_failures = 0
            self._cam_reconnect_cooldown = 0
            return True
        else:
            log.error("Camera reconnect failed, will retry in 30s")
            self._cam_reconnect_cooldown = time.time() + 30
            return False

    def _check_config_reload(self) -> None:
        """Hot-swap the LLM stack when llm.provider / gemini_model /
        claude_model change in the settings table. Called at the top of each
        tick so swaps happen at a natural boundary: no in-flight analyze call
        is torn down mid-request because each _tick() holds local references
        that finish on the old provider before the next tick rebinds them.

        Only the LLM stack is rebuilt:
          - provider (or None in external mode)
          - FrameAnalyzer, Transcriber, SummaryGenerator, ReportGenerator,
            KnowledgeGenerator
          - RagServer (always rebuilt when the LLM config changed, because
            RagEngine captures its own provider at __init__ and has no
            public setter)

        Everything else — capture, presence, embedding, chat, notify — stays
        pinned to the startup Config. Embedding in particular must NOT be
        hot-swapped: embedding.dimensions is baked into the vec_items schema
        at DB open time. Presence / embedding / knowledge also have cached
        booleans derived at __init__ that would become inconsistent if we
        replaced self._config wholesale. To keep the invariant narrow we only
        overwrite self._config.llm, nothing else.
        """
        try:
            new_cfg = Config.load_from_db(self._config.db_path)
        except Exception:
            log.exception("Failed to reload config from DB")
            return

        old_llm = self._config.llm
        new_llm = new_cfg.llm
        if (
            new_llm.provider == old_llm.provider
            and new_llm.gemini_model == old_llm.gemini_model
            and new_llm.claude_model == old_llm.claude_model
        ):
            return

        log.info(
            "Hot-reloading LLM config: provider=%s→%s gemini_model=%s→%s claude_model=%s→%s",
            old_llm.provider,
            new_llm.provider,
            old_llm.gemini_model,
            new_llm.gemini_model,
            old_llm.claude_model,
            new_llm.claude_model,
        )

        # Build the new provider before touching any live instances so a
        # construction failure leaves the old stack untouched.
        if new_llm.provider == "external":
            provider = None
        else:
            try:
                provider = create_provider(
                    new_llm.provider,
                    claude_model=new_llm.claude_model,
                    gemini_model=new_llm.gemini_model,
                )
            except Exception as exc:
                log.exception("Failed to create new provider %s — keeping old config", new_llm.provider)
                self._ws.broadcast(
                    WSEvent(
                        "llm_error",
                        {
                            "message": _scrub_secrets(str(exc))[:200],
                            "consecutive_failures": 0,
                            "provider": new_llm.provider,
                        },
                    )
                )
                return

        # Only the llm subtree of self._config is authoritative post-reload.
        # Update it *before* constructing the RAG server so the new engine
        # sees the new provider/model when it calls create_provider() itself.
        self._config.llm.provider = new_llm.provider
        self._config.llm.gemini_model = new_llm.gemini_model
        self._config.llm.claude_model = new_llm.claude_model

        # Swap the provider-dependent instances. Attribute writes are atomic
        # under the GIL, so any tick currently holding a local reference to
        # the old instance finishes cleanly on the old provider.
        if provider is not None:
            self._transcriber = Transcriber(
                provider,
                context_path=self._config.data_dir / "context.md",
            )
            self._frame_analyzer = FrameAnalyzer(provider, self._config.data_dir, self._db, self._activity_mgr)
            self._summary_gen = SummaryGenerator(provider, self._db, self._config.data_dir)
            self._report_gen = ReportGenerator(provider, self._db, self._config.data_dir, self._activity_mgr)
            self._knowledge_gen = KnowledgeGenerator(provider, self._db, self._config.data_dir)
        else:
            self._transcriber = None
            self._frame_analyzer = None
            self._summary_gen = None
            self._report_gen = None
            self._knowledge_gen = None

        # RagEngine caches its own provider at __init__, so any LLM change
        # (including same-provider model-only changes) must rebuild the RAG
        # server. Always stop whatever is running first, then conditionally
        # start a fresh one when not in external mode.
        if self._rag_server is not None:
            try:
                self._rag_server.stop()
            except Exception:
                log.exception("Failed to stop RAG server during reload")
            self._rag_server = None
        if new_llm.provider != "external":
            try:
                self._rag_server = RagServer(self._config, port=3003)
                self._rag_server.start()
            except Exception:
                log.exception("Failed to start RAG server after reload")
                self._rag_server = None

        self._consecutive_llm_failures = 0

        self._ws.broadcast(
            WSEvent(
                "config_reloaded",
                {
                    "llm_provider": new_llm.provider,
                    "gemini_model": new_llm.gemini_model,
                    "claude_model": new_llm.claude_model,
                },
            )
        )

    def _tick(self):
        self._check_config_reload()
        now = datetime.now()
        self._frame_count += 1

        # Camera capture (optional)
        raw_frame = None
        if self._has_camera:
            with self._cam_lock:
                raw_frame = self._camera.capture()
            if raw_frame is None:
                self._consecutive_cam_failures += 1
                log.warning("Camera capture failed (%d consecutive)", self._consecutive_cam_failures)
                if self._consecutive_cam_failures >= 3:
                    self._try_reconnect_camera()
            else:
                self._consecutive_cam_failures = 0

        # Collect audio from previous interval (recorded during sleep)
        audio_path, transcription = self._collect_audio()

        # Start recording audio for the next interval (runs during processing + sleep)
        self._start_audio_recording(now)

        # Save webcam frame (if available) + screen capture + window info
        rel_path = ""
        if raw_frame is not None:
            rel_path = self._frame_store.save(raw_frame, now)
            # Write latest frame for live web feed
            live_dir = self._config.data_dir / "live"
            live_dir.mkdir(exist_ok=True)
            shutil.copy2(str(self._config.data_dir / rel_path), str(live_dir / "latest.jpg"))

        screen_path = self._screen.capture(now) or ""
        proc_name, win_title = self._window.current()
        foreground_window = f"{proc_name}|{win_title}" if proc_name else ""
        idle_seconds = self._window.idle_seconds()

        # Local lightweight analysis (requires camera)
        brightness = 0.0
        scene_type = SceneType.NORMAL
        motion_score = 0.0
        has_face: bool | None = None
        pose_data = ""

        if raw_frame is not None:
            brightness = self._scene.get_brightness(raw_frame)
            scene_type = self._scene.classify(brightness)
            motion_score = self._motion.analyze(raw_frame)

            # Pose detection
            pose_result = self._pose.detect(raw_frame)
            if pose_result.detected:
                pose_data = pose_result.to_json()
                log.info("Pose: %s (conf=%.2f)", pose_result.posture, pose_result.confidence)

            # Presence detection
            if self._presence_enabled:
                has_face = self._presence.detect_face(raw_frame)
                prev_state = self._presence.state
                self._presence.update(brightness, motion_score, has_face, now, idle_seconds)
                new_state = self._presence.state

                if new_state != prev_state:
                    log.info("Presence: %s -> %s", prev_state.value, new_state.value)
                    self._db.insert_event(
                        Event(
                            timestamp=now,
                            event_type="presence_change",
                            description=f"{prev_state.value} → {new_state.value}",
                        )
                    )
                    self._ws.broadcast(
                        WSEvent(
                            "presence_change",
                            {
                                "from": prev_state.value,
                                "to": new_state.value,
                                "timestamp": now.isoformat(),
                            },
                        )
                    )

        # Collect change-detected extra captures from previous interval
        with self._capture_lock:
            extra_screens = list(self._extra_screen_paths)
            extra_cams = list(self._extra_cam_paths)
            self._extra_screen_paths = []
            self._extra_cam_paths = []

        if extra_screens or extra_cams:
            log.info("Change captures: %d screens, %d cams", len(extra_screens), len(extra_cams))

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
            foreground_window=foreground_window,
            pose_data=pose_data,
            idle_seconds=idle_seconds,
        )
        frame_id = self._db.insert_frame(frame)
        frame.id = frame_id

        # Broadcast new frame via WebSocket
        self._ws.broadcast(
            WSEvent(
                "new_frame",
                {
                    "frame_id": frame_id,
                    "timestamp": now.isoformat(),
                    "path": rel_path,
                    "screen_path": screen_path,
                    "audio_path": audio_path,
                    "has_transcription": bool(transcription),
                    "foreground_window": foreground_window,
                },
            )
        )

        # Scene change event (requires camera)
        if raw_frame is not None:
            if self._last_scene and scene_type != self._last_scene:
                self._db.insert_event(
                    Event(
                        timestamp=now,
                        event_type="scene_change",
                        description=f"{self._last_scene.value} → {scene_type.value}",
                        frame_id=frame_id,
                    )
                )
            self._last_scene = scene_type

            # Motion spike event
            if motion_score > self._config.analysis.motion_threshold * 5:
                self._db.insert_event(
                    Event(
                        timestamp=now,
                        event_type="motion_spike",
                        description=f"大きな動き検知 (score={motion_score:.3f})",
                        frame_id=frame_id,
                    )
                )

        pose_label = ""
        if pose_data:
            from daemon.analysis.pose import PoseResult

            pr = PoseResult.from_json(pose_data)
            pose_label = pr.posture

        log.info(
            "frame=%d bright=%.0f motion=%.3f scene=%s presence=%s pose=%s audio=%s window=%s idle=%ds",
            self._frame_count,
            brightness,
            motion_score,
            scene_type.value,
            self._presence.state.value if self._presence_enabled else "n/a",
            pose_label or "n/a",
            "yes" if audio_path else "no",
            proc_name or "n/a",
            idle_seconds,
        )

        # LLM frame analysis (with change-detected extra captures + presence/pose hints)
        if self._config.llm.provider == "external":
            # External mode: skip LLM, broadcast analysis request via WebSocket
            image_paths = [p for p in [rel_path, screen_path, *extra_screens, *extra_cams] if p]
            self._ws.broadcast(
                WSEvent(
                    "analyze_request",
                    {
                        "frame_id": frame_id,
                        "timestamp": now.isoformat(),
                        "image_paths": image_paths,
                        "data_dir": str(self._config.data_dir.resolve()),
                        "transcription": transcription,
                        "foreground_window": foreground_window,
                        "idle_seconds": idle_seconds,
                        "has_face": has_face,
                        "pose_data": pose_data,
                    },
                )
            )
            description, activity = "", ""
        else:
            all_extra_screens = extra_screens or None
            all_extra_cams = extra_cams or None
            llm_error_msg = ""
            try:
                description, activity = self._frame_analyzer.analyze(
                    frame,
                    all_extra_screens,
                    all_extra_cams,
                    has_face=has_face,
                    pose_data=pose_data,
                    idle_seconds=idle_seconds,
                )
                if description or activity:
                    self._consecutive_llm_failures = 0
                else:
                    self._consecutive_llm_failures += 1
                    llm_error_msg = "LLM returned empty response"
            except Exception as exc:
                log.exception("LLM analysis failed")
                description, activity = "", ""
                self._consecutive_llm_failures += 1
                llm_error_msg = str(exc)

            if self._consecutive_llm_failures > 0 and self._consecutive_llm_failures <= 3:
                if "401" in llm_error_msg or "403" in llm_error_msg or "API_KEY" in llm_error_msg:
                    error_display = "API key is invalid or not set"
                elif "429" in llm_error_msg or "ResourceExhausted" in llm_error_msg:
                    error_display = "API rate limit exceeded"
                else:
                    # Scrub secrets and truncate before sending to any client.
                    scrubbed = _scrub_secrets(llm_error_msg) if llm_error_msg else ""
                    error_display = scrubbed[:200] if scrubbed else "LLM analysis failed"
                self._ws.broadcast(
                    WSEvent(
                        "llm_error",
                        {
                            "message": error_display,
                            "consecutive_failures": self._consecutive_llm_failures,
                            "provider": self._config.llm.provider,
                        },
                    )
                )

        if description or activity:
            self._db.update_frame_analysis(frame_id, description, activity)
            log.info("Analysis: [%s] %s", activity, description[:80])
            self._ws.broadcast(
                WSEvent(
                    "frame_analyzed",
                    {
                        "frame_id": frame_id,
                        "activity": activity,
                        "description": description[:200],
                    },
                )
            )

        # Multimodal embedding (after LLM analysis so description/activity are available)
        # Skip in external mode — embedding runs when Claude Code sends analysis via WS
        if self._embedding_enabled and self._config.llm.provider != "external":
            # Update frame with analysis results for embedding
            frame.claude_description = description
            frame.activity = activity
            self._embed_frame(frame)

        # Multi-scale summaries (skip in external mode — Claude Code generates them)
        if self._config.llm.provider != "external":
            self._check_summaries(now)

        # Embed pending chat messages and summaries (background threads)
        if self._embedding_enabled:
            self._embed_pending_chat(now)
            self._embed_pending_summaries(now)

        # Knowledge profile generation (skip in external mode)
        if self._knowledge_gen:
            self._check_knowledge(now)

        # Auto-generate daily report when day changes (skip in external mode)
        today_str = now.strftime("%Y-%m-%d")
        if self._report_gen and today_str != self._last_report_date:
            yesterday = (now - timedelta(days=1)).date()
            existing = self._db.get_report(yesterday)
            if not existing:
                log.info("Generating daily report for %s...", yesterday)
                report = self._report_gen.generate(yesterday)
                if report:
                    self._send_report_notification(yesterday, report)
            self._last_report_date = today_str

        # Daily retention cleanup
        self._check_retention(now)

    def _embed_frame(self, frame: Frame):
        """Generate and store multimodal embedding for a frame in background thread."""

        def _do_embed():
            try:
                embedding = self._embedder.embed_frame(frame, self._config.data_dir)
                if embedding and frame.id:
                    preview = frame.claude_description[:200] if frame.claude_description else frame.activity
                    self._db.insert_embedding(
                        "frame",
                        frame.id,
                        frame.timestamp.isoformat(),
                        preview,
                        embedding,
                    )
            except Exception:
                log.exception("Embedding failed for frame %s", frame.id)

        threading.Thread(target=_do_embed, daemon=True, name="embed-frame").start()

    def _embed_pending_chat(self, now: datetime):
        """Embed any recent chat messages that don't have embeddings yet."""
        since = now - timedelta(hours=1)
        msg_ids = self._db.get_unembedded_chat_ids(since, limit=10)
        if not msg_ids:
            return

        def _do_embed():
            for mid in msg_ids:
                try:
                    row = self._db._conn.execute("SELECT * FROM chat_messages WHERE id = ?", (mid,)).fetchone()
                    if not row:
                        continue
                    msg = self._db._row_to_chat_message(row)
                    embedding = self._embedder.embed_chat_message(msg)
                    if embedding:
                        preview = f"{msg.author_name}: {msg.content[:200]}"
                        self._db.insert_embedding(
                            "chat",
                            mid,
                            msg.timestamp.isoformat(),
                            preview,
                            embedding,
                        )
                        log.info("Embedded chat %d: %s", mid, preview[:60])
                except Exception:
                    log.exception("Chat embedding failed for message %d", mid)

        threading.Thread(target=_do_embed, daemon=True, name="embed-chat").start()

    def _embed_pending_summaries(self, now: datetime):
        """Embed any recent summaries that don't have embeddings yet."""
        since = now - timedelta(hours=24)
        sum_ids = self._db.get_unembedded_summary_ids(since, limit=5)
        if not sum_ids:
            return

        def _do_embed():
            for sid in sum_ids:
                try:
                    row = self._db._conn.execute("SELECT * FROM summaries WHERE id = ?", (sid,)).fetchone()
                    if not row:
                        continue
                    summary = self._db._row_to_summary(row)
                    embedding = self._embedder.embed_summary(summary)
                    if embedding:
                        preview = f"[{summary.scale}] {summary.content[:200]}"
                        self._db.insert_embedding(
                            "summary",
                            sid,
                            summary.timestamp.isoformat(),
                            preview,
                            embedding,
                        )
                        log.info("Embedded summary %d [%s]", sid, summary.scale)
                except Exception:
                    log.exception("Summary embedding failed for %d", sid)

        threading.Thread(target=_do_embed, daemon=True, name="embed-summary").start()

    def _check_retention(self, now: datetime):
        """Run retention cleanup once per day."""
        today_str = now.strftime("%Y-%m-%d")
        if today_str == self._last_cleanup_date:
            return
        retention_days = self._config.retention_days
        if retention_days <= 0:
            self._last_cleanup_date = today_str
            return
        try:
            cleanup_old_data(self._db, self._config.data_dir, retention_days)
        except Exception:
            log.exception("Retention cleanup failed")
        self._last_cleanup_date = today_str

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
                self._ws.broadcast(
                    WSEvent(
                        "new_summary",
                        {
                            "summary_id": summary.id,
                            "scale": scale,
                            "timestamp": now.isoformat(),
                            "content": summary.content[:200],
                            "frame_count": summary.frame_count,
                        },
                    )
                )

    def _check_knowledge(self, now: datetime):
        """Generate knowledge profile if interval has elapsed."""
        last_time = self._db.get_latest_knowledge_time()
        if last_time:
            elapsed = (now - last_time).total_seconds()
            if elapsed < self._knowledge_interval_days * 86400:
                return

        log.info("Generating knowledge profile...")
        try:
            self._knowledge_gen.generate()
        except Exception:
            log.exception("Knowledge generation failed")

    def _send_report_notification(self, report_date, report):
        """Send daily report via configured notification channel."""
        title = f"vida Daily Report — {report_date.isoformat()}"
        body = f"{report.content}\n\n{report.frame_count} frames | Focus {report.focus_pct:.0f}%"
        send_notification(self._config.notify, title, body)

    def _write_status(self, llm_error: str = "") -> None:
        """Write daemon status to data/status.json for web UI."""
        status = {
            "running": True,
            "camera": self._has_camera,
            "mic": self._has_mic,
            "started_at": datetime.now().isoformat(),
            "llm_provider": self._config.llm.provider,
            "llm_error": llm_error,
        }
        status_path = self._config.data_dir / "status.json"
        status_path.write_text(json.dumps(status))

    def _secure_data_dir(self) -> None:
        """Best-effort tighten permissions on the data directory and DB.

        On POSIX we chmod 700 the directory and 600 the database file so
        another user on the machine can't read captured frames / keys.
        On Windows the default ACL already limits access to the owner.
        """
        if os.name != "posix":
            return
        try:
            data_dir = self._config.data_dir
            data_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(data_dir, 0o700)
            db_path = self._config.db_path
            if db_path.exists():
                os.chmod(db_path, 0o600)
            # SQLite WAL/SHM sidecars
            for suffix in ("-wal", "-shm"):
                sidecar = db_path.with_name(db_path.name + suffix)
                if sidecar.exists():
                    os.chmod(sidecar, 0o600)
        except Exception:
            log.exception("Failed to tighten data dir permissions")

    def _write_pid(self):
        self._config.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self._config.pid_file.write_text(str(os.getpid()))
        if os.name == "posix":
            with contextlib.suppress(Exception):
                os.chmod(self._config.pid_file, 0o600)

    def _cleanup_pid(self):
        if self._config.pid_file.exists():
            self._config.pid_file.unlink()

    def _handle_ws_message(self, data: dict, ws) -> None:
        """Handle incoming WebSocket messages from clients (Claude Code, UI)."""
        msg_type = data.get("type", "")

        if msg_type == "frame_analysis":
            # Claude Code sending analysis result
            frame_id = data.get("frame_id")
            description = data.get("description", "")
            activity = data.get("activity", "")
            meta_category = data.get("meta_category", "other")
            if frame_id and (description or activity) and self._db.get_frame_by_id(frame_id):
                if activity:
                    activity, _ = self._activity_mgr.normalize_and_register(activity, meta_category)
                self._db.update_frame_analysis(frame_id, description, activity)
                log.info("External analysis for frame %d: [%s] %s", frame_id, activity, description[:80])
                self._ws.broadcast(
                    WSEvent(
                        "frame_analyzed",
                        {
                            "frame_id": frame_id,
                            "activity": activity,
                            "description": description[:200],
                            "source": "external",
                        },
                    )
                )

        elif msg_type == "create_summary":
            # Claude Code sending a summary
            scale = data.get("scale", "")
            content = data.get("content", "")
            frame_count = data.get("frame_count", 0)
            if scale and content and scale in SCALES:
                from daemon.storage.models import Summary

                summary = Summary(
                    timestamp=datetime.now(),
                    scale=scale,
                    content=content,
                    frame_count=frame_count,
                )
                summary.id = self._db.insert_summary(summary)
                log.info("External summary [%s]: %s", scale, content[:80])
                self._ws.broadcast(
                    WSEvent(
                        "new_summary",
                        {
                            "summary_id": summary.id,
                            "scale": scale,
                            "content": content[:200],
                            "source": "external",
                        },
                    )
                )

    def _handle_signal(self, signum, _frame):
        log.info("Received signal %d, stopping...", signum)
        self._running = False
