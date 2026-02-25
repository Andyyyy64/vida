from __future__ import annotations

import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

log = logging.getLogger(__name__)


class LiveServer:
    """MJPEG streaming server for live webcam feed."""

    def __init__(self, port: int = 3002):
        self._port = port
        self._latest_jpeg: bytes | None = None
        self._lock = threading.Lock()
        self._running = False
        self._httpd: HTTPServer | None = None

    def update_frame(self, jpeg_bytes: bytes):
        with self._lock:
            self._latest_jpeg = jpeg_bytes

    def start(self):
        self._running = True
        thread = threading.Thread(target=self._serve, daemon=True)
        thread.start()
        log.info("Live MJPEG server on port %d", self._port)

    def stop(self):
        self._running = False
        if self._httpd:
            self._httpd.shutdown()

    def _serve(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/stream":
                    self.send_error(404)
                    return

                self.send_response(200)
                self.send_header(
                    "Content-Type", "multipart/x-mixed-replace; boundary=frame"
                )
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                try:
                    while server._running:
                        with server._lock:
                            jpeg = server._latest_jpeg
                        if jpeg:
                            self.wfile.write(b"--frame\r\n")
                            self.wfile.write(b"Content-Type: image/jpeg\r\n\r\n")
                            self.wfile.write(jpeg)
                            self.wfile.write(b"\r\n")
                        time.sleep(0.1)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def log_message(self, format, *args):
                pass

        self._httpd = HTTPServer(("0.0.0.0", self._port), Handler)
        self._httpd.serve_forever()
