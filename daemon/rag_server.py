from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from daemon.config import Config
from daemon.rag import RagEngine

log = logging.getLogger(__name__)


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
            def do_POST(self) -> None:
                if self.path != "/ask":
                    self.send_error(404)
                    return

                content_len = int(self.headers.get("Content-Length", 0))
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

                history = data.get("history", [])

                try:
                    result = engine.ask(query, history=history)
                    self._send_json(result)
                except Exception:
                    log.exception("RAG request failed")
                    self._send_json({"error": "internal error"}, 500)

            def do_OPTIONS(self) -> None:
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def _send_json(self, data: dict, status: int = 200) -> None:
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                pass  # silence HTTP logs

        self._httpd = _ThreadedHTTPServer(("0.0.0.0", self._port), Handler)
        self._httpd.serve_forever()
