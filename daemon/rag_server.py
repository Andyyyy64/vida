from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from daemon.config import Config
from daemon.live import _host_allowed, _origin_allowed  # reuse loopback header checks
from daemon.rag import RagEngine

log = logging.getLogger(__name__)

# Reject request bodies larger than this (defense against memory exhaustion).
_MAX_BODY_BYTES = 64 * 1024


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class RagServer:
    """HTTP server for RAG chat API (port 3003)."""

    def __init__(self, config: Config, port: int = 3003):
        self._port = port
        self._config = config
        self._engine: RagEngine | None = None
        self._httpd: _ThreadedHTTPServer | None = None

    def start(self) -> None:
        self._engine = RagEngine(self._config)
        thread = threading.Thread(target=self._serve, daemon=True)
        thread.start()
        log.info("RAG server on port %d", self._port)

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
        if self._engine:
            self._engine.close()

    def _serve(self) -> None:
        engine = self._engine

        class Handler(BaseHTTPRequestHandler):
            def _check_headers(self) -> bool:
                if not _host_allowed(self.headers.get("Host")):
                    self.send_error(421)
                    return False
                if not _origin_allowed(self.headers.get("Origin")):
                    self.send_error(403)
                    return False
                return True

            def do_POST(self) -> None:
                if not self._check_headers():
                    return
                if self.path != "/ask":
                    self.send_error(404)
                    return

                try:
                    content_len = int(self.headers.get("Content-Length", 0))
                except ValueError:
                    self.send_error(400)
                    return
                if content_len <= 0 or content_len > _MAX_BODY_BYTES:
                    self.send_error(413)
                    return
                body = self.rfile.read(content_len)

                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    self._send_json({"error": "invalid JSON"}, 400)
                    return

                query = data.get("query", "").strip()
                if not query:
                    self._send_json({"error": "query is required"}, 400)
                    return
                # Hard cap on query length to avoid LLM/FTS abuse.
                if len(query) > 2000:
                    self._send_json({"error": "query too long"}, 400)
                    return

                history = data.get("history", [])
                if not isinstance(history, list) or len(history) > 100:
                    self._send_json({"error": "invalid history"}, 400)
                    return

                try:
                    result = engine.ask(query, history=history)
                    self._send_json(result)
                except Exception:
                    log.exception("RAG request failed")
                    self._send_json({"error": "internal error"}, 500)

            def do_OPTIONS(self) -> None:
                # CORS preflight — only allow known loopback origins.
                origin = self.headers.get("Origin", "")
                if not _origin_allowed(origin):
                    self.send_error(403)
                    return
                self.send_response(204)
                if origin:
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def _send_json(self, data: dict, status: int = 200) -> None:
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Content-Type-Options", "nosniff")
                origin = self.headers.get("Origin", "")
                if origin and _origin_allowed(origin):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                pass  # silence HTTP logs

        # Bind to loopback only.
        self._httpd = _ThreadedHTTPServer(("127.0.0.1", self._port), Handler)
        self._httpd.serve_forever()
