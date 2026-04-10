"""End-to-end tests for the WebSocket server (:mod:`daemon.ws_server`).

Uses the real ``websockets`` client library to drive the real server.
These tests are async because ``websockets`` is async-only.
"""

from __future__ import annotations

import asyncio
import json

import pytest
import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

# Only the `e2e` marker is applied at module level. Async tests are
# auto-marked by pytest-asyncio via ``asyncio_mode = "auto"`` in
# pyproject.toml, so the sync ``test_ws_server_binds_loopback_only`` below
# doesn't need to claim to be async.
pytestmark = pytest.mark.e2e


def _url(port: int) -> str:
    return f"ws://127.0.0.1:{port}"


# ── bind ───────────────────────────────────────────────────────────────────


def test_ws_server_binds_loopback_only(ws_server):
    """The websockets server exposes its sockets — all must be loopback."""
    inner = ws_server._server  # type: ignore[attr-defined]
    assert inner is not None
    # websockets 15 exposes .sockets via the underlying asyncio.Server
    sockets = getattr(inner, "sockets", None)
    if sockets is None:
        # Older shape: ._server holds the asyncio server which has sockets
        sockets = inner._server.sockets  # type: ignore[attr-defined]
    addrs = {sock.getsockname()[0] for sock in sockets}
    assert addrs, "expected at least one listening socket"
    for addr in addrs:
        assert addr in ("127.0.0.1", "::1"), f"WS bound to non-loopback {addr!r}"


# ── handshake Origin enforcement ───────────────────────────────────────────


async def _recv_welcome(ws) -> dict:
    raw = await asyncio.wait_for(ws.recv(), timeout=2)
    return json.loads(raw)


async def test_connect_with_good_origin(ws_server):
    async with websockets.connect(
        _url(ws_server._port), origin="http://127.0.0.1:5173"
    ) as ws:
        welcome = await _recv_welcome(ws)
        assert welcome["type"] == "connected"
        assert welcome["server"] == "vida-daemon"


async def test_connect_without_origin(ws_server):
    """Native clients (Claude Code CLI) don't send Origin — must work."""
    async with websockets.connect(_url(ws_server._port)) as ws:
        welcome = await _recv_welcome(ws)
        assert welcome["type"] == "connected"


async def test_connect_with_tauri_origin(ws_server):
    async with websockets.connect(
        _url(ws_server._port), origin="http://tauri.localhost"
    ) as ws:
        welcome = await _recv_welcome(ws)
        assert welcome["type"] == "connected"


async def test_connect_with_bad_origin_rejected(ws_server):
    with pytest.raises(InvalidStatus) as exc:
        async with websockets.connect(
            _url(ws_server._port), origin="http://evil.com"
        ):
            pass
    assert exc.value.response.status_code == 403


async def test_connect_with_other_port_origin_rejected(ws_server):
    """A different scheme/host combo must be rejected, not just 'evil.com'."""
    with pytest.raises(InvalidStatus):
        async with websockets.connect(
            _url(ws_server._port), origin="https://example.org"
        ):
            pass


# ── message whitelist ──────────────────────────────────────────────────────


async def test_ping_returns_pong(ws_server):
    async with websockets.connect(_url(ws_server._port)) as ws:
        await _recv_welcome(ws)
        await ws.send(json.dumps({"type": "ping"}))
        reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert reply["type"] == "pong"
        assert "clients" in reply


async def test_unknown_message_type_rejected(ws_server):
    async with websockets.connect(_url(ws_server._port)) as ws:
        await _recv_welcome(ws)
        await ws.send(json.dumps({"type": "evil_admin_cmd", "payload": "pwn"}))
        reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert reply["type"] == "error"
        assert "unsupported" in reply["message"].lower()


async def test_invalid_json_rejected(ws_server):
    async with websockets.connect(_url(ws_server._port)) as ws:
        await _recv_welcome(ws)
        await ws.send("{not valid json")
        reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert reply["type"] == "error"


async def test_allowed_message_type_no_handler(ws_server):
    """frame_analysis is on the whitelist — with no handler attached it
    must still NOT be rejected as 'unsupported' (only the handler is
    missing)."""
    async with websockets.connect(_url(ws_server._port)) as ws:
        await _recv_welcome(ws)
        await ws.send(json.dumps({"type": "frame_analysis", "frame_id": 1}))
        # No handler attached in the fixture, so no synchronous reply.
        # Give the server a moment, then send a ping to confirm the
        # connection is still alive (no disconnect triggered).
        await asyncio.sleep(0.1)
        await ws.send(json.dumps({"type": "ping"}))
        reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert reply["type"] == "pong"


# ── broadcast fan-out ──────────────────────────────────────────────────────


async def test_broadcast_to_multiple_clients(ws_server):
    from daemon.ws_server import WSEvent

    async with websockets.connect(_url(ws_server._port)) as a, websockets.connect(
        _url(ws_server._port)
    ) as b:
        await _recv_welcome(a)
        await _recv_welcome(b)

        # Give the server a moment to update its client set after the
        # second connection's welcome is dispatched.
        await asyncio.sleep(0.05)

        ws_server.broadcast(WSEvent("frame_analyzed", {"frame_id": 42}))

        msg_a = json.loads(await asyncio.wait_for(a.recv(), timeout=2))
        msg_b = json.loads(await asyncio.wait_for(b.recv(), timeout=2))
        assert msg_a["type"] == "frame_analyzed"
        assert msg_b["type"] == "frame_analyzed"
        assert msg_a["frame_id"] == 42


# ── message size cap ───────────────────────────────────────────────────────


async def test_oversized_frame_rejected(ws_server):
    """Server ``max_size=256 KiB``; larger frames must close the connection."""
    async with websockets.connect(_url(ws_server._port)) as ws:
        await _recv_welcome(ws)
        with pytest.raises(ConnectionClosed):
            await ws.send("x" * (300 * 1024))
            # Wait for the server to close in response.
            await asyncio.wait_for(ws.recv(), timeout=2)
