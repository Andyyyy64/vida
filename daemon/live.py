from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

log = logging.getLogger(__name__)

# Allowed Host headers — prevents DNS rebinding attacks against localhost services.
# Any Host that doesn't match one of these is rejected.
_ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "[::1]",
        "::1",
    }
)
# Allowed Origin values for browser requests (Tauri WebView + dev server).
# Empty/missing Origin is allowed (native callers like <img src> don't set it).
_ALLOWED_ORIGINS: frozenset[str] = frozenset(
    {
        "http://localhost",
        "http://127.0.0.1",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "null",
    }
)


def _host_allowed(host_header: str | None) -> bool:
    if not host_header:
        return False
    # Strip port
    host = host_header.rsplit(":", 1)[0] if host_header.count(":") == 1 else host_header
    # IPv6 literal like [::1]:3002
    if host_header.startswith("["):
        host = host_header.split("]", 1)[0] + "]"
    return host in _ALLOWED_HOSTS


def _origin_allowed(origin_header: str | None) -> bool:
    if not origin_header:
        return True  # no Origin = non-browser or same-origin
    # Strip port from origin (http://127.0.0.1:5173 -> http://127.0.0.1)
    try:
        scheme, rest = origin_header.split("://", 1)
        host = rest.split(":", 1)[0].split("/", 1)[0]
        return f"{scheme}://{host}" in _ALLOWED_ORIGINS or origin_header == "null"
    except ValueError:
        return False


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
            def _reject(self, code: int, msg: str) -> None:
                self.send_response(code)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _check_headers(self) -> bool:
                # DNS rebinding protection: reject requests whose Host header
                # doesn't match a known loopback name.
                if not _host_allowed(self.headers.get("Host")):
                    self._reject(421, "bad host")
                    return False
                if not _origin_allowed(self.headers.get("Origin")):
                    self._reject(403, "bad origin")
                    return False
                return True

            def do_GET(self) -> None:
                if not self._check_headers():
                    return
                if self.path == "/health":
                    with server._lock:
                        has_frame = server._latest_jpeg is not None
                    body = json.dumps({"live": has_frame}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                elif self.path == "/stream":
                    use_pose = False
                elif self.path == "/stream/pose":
                    use_pose = True
                else:
                    self.send_error(404)
                    return

                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
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
                            self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                            self.wfile.write(jpeg)
                            self.wfile.write(b"\r\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def log_message(self, format: str, *args: object) -> None:
                pass

        # Bind to loopback only — never expose the raw camera stream to the LAN.
        self._httpd = _ThreadedHTTPServer(("127.0.0.1", self._port), Handler)
        self._httpd.serve_forever()
