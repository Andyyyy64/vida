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
        """Stop the server and close all connections."""
        if self._loop and self._server:
            async def _shutdown():
                self._server.close()
                await self._server.wait_closed()
                self._loop.stop()

            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
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

        try:
            self._server = await websockets.serve(
                self._handler,
                "127.0.0.1",
                self._port,
                ping_interval=30,
                ping_timeout=10,
            )
            log.info("WebSocket server on ws://127.0.0.1:%d", self._port)
            await asyncio.Future()  # run forever
        except OSError as e:
            log.error("WebSocket server failed to start on port %d: %s", self._port, e)
        except asyncio.CancelledError:
            pass

    async def _handler(self, ws) -> None:
        async with self._lock:
            self._clients.add(ws)
        remote = ws.remote_address
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

                # Handle ping inline (no blocking)
                if data.get("type") == "ping":
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
