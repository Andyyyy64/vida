"""End-to-end tests for the MJPEG live server (:mod:`daemon.live`).

Exercises the actual HTTP handler with real sockets to confirm the
security hardening from the audit commit holds:

- Server is bound to 127.0.0.1, not 0.0.0.0
- Host header validation rejects DNS-rebinding attempts
- Origin header validation rejects cross-origin browser requests
- CORS wildcard is not returned on any response
- ``X-Content-Type-Options: nosniff`` is set
- Unknown paths return 404
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.e2e


def _raw_request(
    port: int,
    path: str,
    host_header: str | None = "127.0.0.1",
    origin: str | None = None,
    method: str = "GET",
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Send an HTTP request bypassing urllib's auto-Host header.

    Returns ``(status, headers, body)``. Raises on transport errors.
    """
    req_lines = [f"{method} {path} HTTP/1.1"]
    if host_header is not None:
        req_lines.append(f"Host: {host_header}")
    if origin is not None:
        req_lines.append(f"Origin: {origin}")
    if body is not None:
        req_lines.append(f"Content-Length: {len(body)}")
    req_lines.append("Connection: close")
    req_lines.append("")
    req_lines.append("")
    header_blob = "\r\n".join(req_lines).encode("ascii")
    payload = header_blob + (body or b"")

    with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
        s.sendall(payload)
        chunks: list[bytes] = []
        while True:
            try:
                chunk = s.recv(4096)
            except TimeoutError:
                break
            if not chunk:
                break
            chunks.append(chunk)
            # For /stream we don't want to read forever — bail after we
            # have the headers and a little bit of body.
            if len(b"".join(chunks)) > 16_384:
                break
    raw = b"".join(chunks)
    head, _, body_out = raw.partition(b"\r\n\r\n")
    status_line, *header_lines = head.decode("iso-8859-1").split("\r\n")
    status = int(status_line.split(" ", 2)[1])
    headers = {}
    for line in header_lines:
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
    return status, headers, body_out


# ── bind address ───────────────────────────────────────────────────────────


def test_live_server_binds_loopback_only(live_server):
    """The server address must be 127.0.0.1, never 0.0.0.0 or ::."""
    httpd = live_server._httpd  # type: ignore[attr-defined]
    host, _port = httpd.server_address
    assert host == "127.0.0.1", f"MJPEG server must bind loopback, got {host!r}"


# ── health endpoint ────────────────────────────────────────────────────────


def test_health_ok_with_loopback_host(live_server):
    status, headers, body = _raw_request(live_server._port, "/health", host_header="127.0.0.1")
    assert status == 200
    assert headers.get("content-type", "").startswith("application/json")
    assert headers.get("x-content-type-options") == "nosniff"
    # CORS wildcard must not come back
    assert "access-control-allow-origin" not in headers or headers["access-control-allow-origin"] != "*"
    data = json.loads(body)
    assert "live" in data


def test_health_ok_with_localhost_host(live_server):
    status, _, _ = _raw_request(live_server._port, "/health", host_header="localhost:1234")
    assert status == 200


# ── DNS rebinding / Host header ────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_host",
    [
        "evil.com",
        "evil.com:3002",
        "attacker.local",
        "",
    ],
)
def test_health_rejects_bad_host(live_server, bad_host):
    status, _, _ = _raw_request(live_server._port, "/health", host_header=bad_host or None)
    assert status == 421, f"expected 421 for Host={bad_host!r}, got {status}"


def test_stream_rejects_bad_host(live_server):
    status, _, _ = _raw_request(live_server._port, "/stream", host_header="evil.com")
    assert status == 421


# ── Origin header ──────────────────────────────────────────────────────────


def test_health_rejects_bad_origin(live_server):
    status, _, _ = _raw_request(
        live_server._port, "/health", host_header="127.0.0.1", origin="http://evil.com"
    )
    assert status == 403


def test_health_accepts_empty_origin(live_server):
    """Native clients (e.g. <img src>) don't send Origin — must still work."""
    status, _, _ = _raw_request(live_server._port, "/health", host_header="127.0.0.1", origin=None)
    assert status == 200


def test_health_accepts_tauri_origin(live_server):
    status, _, _ = _raw_request(
        live_server._port,
        "/health",
        host_header="127.0.0.1",
        origin="http://tauri.localhost",
    )
    assert status == 200


# ── routing ────────────────────────────────────────────────────────────────


def test_unknown_path_returns_404(live_server):
    status, _, _ = _raw_request(live_server._port, "/does-not-exist", host_header="127.0.0.1")
    assert status == 404


def test_stream_endpoint_serves_jpeg(live_server):
    status, headers, body = _raw_request(live_server._port, "/stream", host_header="127.0.0.1")
    assert status == 200
    assert "multipart/x-mixed-replace" in headers.get("content-type", "")
    # Frame we seeded in the fixture should show up
    assert b"\xff\xd8\xff\xd9" in body
