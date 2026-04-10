"""WebSocket server for bidirectional real-time communication.

Allows external clients (Claude Code, Tauri UI) to receive events
and send commands (analysis results, UI actions) to the daemon.

Default port: 3004
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger(__name__)

# Allowed message types for inbound messages. Anything else is rejected.
# Keep this narrow — adding a new type means exposing a new DB write path.
_ALLOWED_MESSAGE_TYPES: frozenset[str] = frozenset({
    "ping",
    "frame_analysis",
    "create_summary",
})

# Allowed Origin values for browser-based clients. Non-browser websocket
# clients (Claude Code, CLI tooling) don't send an Origin header — those are
# allowed through. Browser clients must match one of these exactly.
_ALLOWED_ORIGINS: frozenset[str] = frozenset({
    "http://localhost",
    "http://127.0.0.1",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "null",
})


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    try:
        scheme, rest = origin.split("://", 1)
        host = rest.split(":", 1)[0].split("/", 1)[0]
        return f"{scheme}://{host}" in _ALLOWED_ORIGINS or origin == "null"
    except ValueError:
        return False


@dataclass
class WSEvent:
    """An event to broadcast to all connected clients."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({"type": self.type, **self.data}, ensure_ascii=False)


class WebSocketServer:
    """Async WebSocket server running in a background thread.

    Usage:
        server = WebSocketServer(port=3004)
        server.on_message = my_handler  # optional
        server.start()
        server.broadcast(WSEvent("new_frame", {"id": 123}))
        server.stop()
    """

    def __init__(self, port: int = 3004):
        self._port = port
        self._clients: set = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._server = None
        self.on_message: Callable[[dict, Any], None] | None = None

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def start(self) -> None:
        """Start the WebSocket server in a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="ws-server")
        self._thread.start()

    def stop(self) -> None:
        """Stop the server and close all connections.

        We just ask the running server to close on its own event loop.
        ``_serve()`` is awaiting ``server.wait_closed()``; once that
        future resolves the ``run_until_complete`` call returns cleanly
        and the background thread exits. Calling ``loop.stop()`` directly
        used to race with the pending Future and raised
        ``RuntimeError: Event loop stopped before Future completed``.
        """
        if self._loop and self._server:
            try:
                self._loop.call_soon_threadsafe(self._server.close)
            except RuntimeError:
                pass  # loop already closed
        if self._thread:
            self._thread.join(timeout=3)

    def broadcast(self, event: WSEvent) -> None:
        """Send an event to all connected clients (thread-safe)."""
        if not self._loop or not self._clients:
            return
        msg = event.to_json()
        asyncio.run_coroutine_threadsafe(self._broadcast_async(msg), self._loop)

    async def _broadcast_async(self, msg: str) -> None:
        if not self._clients:
            return
        dead = set()
        async with self._lock:
            for ws in self._clients.copy():
                try:
                    await ws.send(msg)
                except Exception:
                    dead.add(ws)
            self._clients -= dead

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        # Re-create lock on the correct loop
        self._lock = asyncio.Lock()
        self._loop.run_until_complete(self._serve())

    async def _serve(self) -> None:
        try:
            import websockets
        except ImportError:
            log.warning("websockets not installed — WebSocket server disabled. pip install websockets")
            return

        async def _process_request(connection, request):
            # websockets >= 14 passes (connection, request). Reject bad Origins
            # during the HTTP handshake before upgrading to a websocket.
            try:
                origin = request.headers.get("Origin")
            except Exception:
                origin = None
            if not _origin_allowed(origin):
                log.warning("WS rejected: bad Origin=%r", origin)
                return connection.respond(403, "forbidden origin\n")
            return None

        try:
            # Use the async context manager so shutdown can unwind
            # through `wait_closed()` without needing to stop the loop
            # from another thread.
            async with websockets.serve(
                self._handler,
                "127.0.0.1",
                self._port,
                ping_interval=30,
                ping_timeout=10,
                max_size=256 * 1024,  # cap inbound frame size
                process_request=_process_request,
            ) as server:
                self._server = server
                log.info("WebSocket server on ws://127.0.0.1:%d", self._port)
                await server.wait_closed()
        except OSError as e:
            log.error("WebSocket server failed to start on port %d: %s", self._port, e)
        except asyncio.CancelledError:
            pass

    async def _handler(self, ws) -> None:
        # Extra defence in depth: reject any connection whose remote address
        # isn't loopback. (websockets.serve binds to 127.0.0.1 already, but
        # this protects against accidental regressions.)
        remote = ws.remote_address
        if remote and remote[0] not in ("127.0.0.1", "::1", "localhost"):
            log.warning("WS rejected: non-loopback remote %s", remote)
            await ws.close(code=1008, reason="non-loopback")
            return

        async with self._lock:
            self._clients.add(ws)
        log.info("WS client connected: %s (total: %d)", remote, len(self._clients))

        # Send welcome message
        await ws.send(json.dumps({
            "type": "connected",
            "clients": len(self._clients),
            "server": "vida-daemon",
        }))

        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"type": "error", "message": "invalid JSON"}))
                    continue

                msg_type = data.get("type")
                if not isinstance(msg_type, str) or msg_type not in _ALLOWED_MESSAGE_TYPES:
                    await ws.send(json.dumps({"type": "error", "message": "unsupported message type"}))
                    continue

                # Handle ping inline (no blocking)
                if msg_type == "ping":
                    await ws.send(json.dumps({"type": "pong", "clients": self.client_count}))
                    continue

                # Run handler in thread executor to avoid blocking the event loop
                if self.on_message:
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None, self.on_message, data, ws
                        )
                    except Exception:
                        log.exception("Error in on_message handler")
                        await ws.send(json.dumps({"type": "error", "message": "handler error"}))
        except Exception:
            pass  # client disconnected
        finally:
            async with self._lock:
                self._clients.discard(ws)
            log.info("WS client disconnected: %s (total: %d)", remote, len(self._clients))
