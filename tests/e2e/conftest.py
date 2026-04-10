"""Shared fixtures for daemon network-server e2e tests.

These tests boot the real HTTP / WebSocket servers on ephemeral loopback
ports and drive them with real clients (urllib, websockets). They exist to
protect the defense-in-depth work added during the security audit:

    - 127.0.0.1-only bind on ports 3002/3003/3004
    - Host header validation (DNS rebinding defense)
    - Origin header validation
    - Request size / query length caps
    - WebSocket inbound message type whitelist

Because these touch real sockets, they are marked ``@pytest.mark.e2e`` and
can be skipped in constrained environments with ``pytest -m "not e2e"``.
"""

from __future__ import annotations

import socket
import time
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from daemon.live import LiveServer
from daemon.ws_server import WebSocketServer


def _grab_free_port() -> int:
    """Bind a socket to port 0 on loopback and return the OS-assigned port.

    We close the probe socket before returning so the caller can bind it;
    the race window is tiny and acceptable for test-only code.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 3.0) -> None:
    """Block until something is listening on 127.0.0.1:port, or raise."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.05)
    raise RuntimeError(f"port {port} did not open within {timeout}s")


@pytest.fixture
def free_port() -> int:
    return _grab_free_port()


@pytest.fixture
def live_server(free_port: int) -> Iterator[LiveServer]:
    """Boot the MJPEG server on a random loopback port."""
    srv = LiveServer(port=free_port)
    # Seed one frame so /health reports live=true and /stream has data.
    srv.update_frame(b"\xff\xd8\xff\xd9")  # minimal JPEG marker
    srv.start()
    try:
        _wait_for_port(free_port)
        yield srv
    finally:
        srv.stop()


class _StubRagEngine:
    """Replacement for :class:`daemon.rag.RagEngine` that avoids LLM/DB init.

    Keeps a record of received queries so tests can assert the handler
    forwarded them. Returns a deterministic canned response.
    """

    def __init__(self, *_args, **_kwargs) -> None:
        self.queries: list[tuple[str, list]] = []

    def ask(self, query: str, history: list | None = None) -> dict:
        self.queries.append((query, list(history or [])))
        return {"response": f"stub: {query}", "sources": []}

    def close(self) -> None:
        pass


@pytest.fixture
def rag_server(free_port: int) -> Iterator[tuple[object, _StubRagEngine]]:
    """Boot the RAG HTTP server with a stubbed engine (no LLM/DB required)."""
    # Import here so the patch target is resolved after daemon.rag_server
    # is importable.
    from daemon import rag_server as rag_module

    stub_factory = MagicMock(side_effect=lambda _config: _StubRagEngine())

    # Patch BOTH the symbol used inside rag_server.py and the underlying
    # module attribute so new instances see the stub.
    with patch.object(rag_module, "RagEngine", stub_factory):
        config = MagicMock()  # RagServer only stores it and passes to engine
        srv = rag_module.RagServer(config, port=free_port)
        srv.start()
        try:
            _wait_for_port(free_port)
            # stub_factory was called inside start(); grab the instance
            engine_instance = stub_factory.return_value
            # Because side_effect returns a fresh stub each call, the first
            # call result is what RagServer stored.
            engine_instance = srv._engine  # type: ignore[attr-defined]
            yield srv, engine_instance
        finally:
            srv.stop()


@pytest.fixture
def ws_server(free_port: int) -> Iterator[WebSocketServer]:
    """Boot the WebSocket server on a random loopback port."""
    srv = WebSocketServer(port=free_port)
    srv.start()
    try:
        _wait_for_port(free_port)
        yield srv
    finally:
        srv.stop()
