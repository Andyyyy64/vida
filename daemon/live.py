from __future__ import annotations

import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

log = logging.getLogger(__name__)


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each MJPEG client connection in its own thread."""
    daemon_threads = True
    allow_reuse_address = True


class LiveServer:
    """MJPEG streaming server for live webcam feed.

    Supports two streams:
      /stream      — original camera feed
      /stream/pose — camera feed with pose skeleton overlay
    """

    def __init__(self, port: int = 3002):
        self._port = port
        self._latest_jpeg: bytes | None = None
        self._latest_jpeg_pose: bytes | None = None
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._running = False
        self._httpd: _ThreadedHTTPServer | None = None

    def update_frame(self, jpeg_bytes: bytes, jpeg_pose_bytes: bytes | None = None) -> None:
        with self._lock:
            self._latest_jpeg = jpeg_bytes
            if jpeg_pose_bytes is not None:
                self._latest_jpeg_pose = jpeg_pose_bytes
        # Wake all waiting clients instantly
        self._event.set()
        self._event.clear()

    def start(self) -> None:
        self._running = True
        thread = threading.Thread(target=self._serve, daemon=True)
        thread.start()
        log.info("Live MJPEG server on port %d", self._port)

    def stop(self) -> None:
        self._running = False
        self._event.set()  # unblock any waiting clients
        if self._httpd:
            self._httpd.shutdown()

    def _serve(self) -> None:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/stream":
                    use_pose = False
                elif self.path == "/stream/pose":
                    use_pose = True
                else:
                    self.send_error(404)
                    return

                self.send_response(200)
                self.send_header(
                    "Content-Type", "multipart/x-mixed-replace; boundary=frame"
                )
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                last_id: int | None = None
                try:
                    while server._running:
                        # Wait for a new frame (up to 1s timeout to check _running)
                        server._event.wait(timeout=1.0)
                        with server._lock:
                            if use_pose and server._latest_jpeg_pose:
                                jpeg = server._latest_jpeg_pose
                            else:
                                jpeg = server._latest_jpeg
                            frame_id = id(jpeg)
                        if jpeg and frame_id != last_id:
                            last_id = frame_id
                            self.wfile.write(b"--frame\r\n")
                            self.wfile.write(b"Content-Type: image/jpeg\r\n")
                            self.wfile.write(
                                f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                            )
                            self.wfile.write(jpeg)
                            self.wfile.write(b"\r\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def log_message(self, format: str, *args: object) -> None:
                pass

        self._httpd = _ThreadedHTTPServer(("0.0.0.0", self._port), Handler)
        self._httpd.serve_forever()
