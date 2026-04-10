"""End-to-end tests for the RAG HTTP server (:mod:`daemon.rag_server`).

The real RagEngine is replaced with a stub in the fixture so the tests
hit only the HTTP boundary — which is where all the security invariants
live anyway:

- 127.0.0.1 bind
- Host / Origin validation
- Content-Length sanity and size cap
- Query length and history length caps
- Unknown path / method rejected
- OPTIONS preflight only from allowed origins
"""

from __future__ import annotations

import json
import socket

import pytest

pytestmark = pytest.mark.e2e


def _request(
    port: int,
    path: str,
    method: str = "POST",
    host: str | None = "127.0.0.1",
    origin: str | None = None,
    body: bytes | None = None,
    content_length_override: int | None = None,
) -> tuple[int, dict[str, str], bytes]:
    lines = [f"{method} {path} HTTP/1.1"]
    if host is not None:
        lines.append(f"Host: {host}")
    if origin is not None:
        lines.append(f"Origin: {origin}")
    if body is not None:
        cl = content_length_override if content_length_override is not None else len(body)
        lines.append(f"Content-Length: {cl}")
        lines.append("Content-Type: application/json")
    lines.append("Connection: close")
    lines.append("")
    lines.append("")
    head = "\r\n".join(lines).encode("ascii")
    payload = head + (body or b"")

    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
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
    raw = b"".join(chunks)
    head_bytes, _, body_bytes = raw.partition(b"\r\n\r\n")
    status_line, *header_lines = head_bytes.decode("iso-8859-1").split("\r\n")
    status = int(status_line.split(" ", 2)[1])
    headers = {}
    for line in header_lines:
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
    return status, headers, body_bytes


def _ask_body(query: str, history: list | None = None) -> bytes:
    return json.dumps({"query": query, "history": history or []}).encode()


# ── bind ───────────────────────────────────────────────────────────────────


def test_rag_server_binds_loopback_only(rag_server):
    srv, _engine = rag_server
    httpd = srv._httpd  # type: ignore[attr-defined]
    assert httpd.server_address[0] == "127.0.0.1"


# ── happy path ─────────────────────────────────────────────────────────────


def test_ask_happy_path(rag_server):
    srv, engine = rag_server
    status, headers, body = _request(srv._port, "/ask", body=_ask_body("hello"))
    assert status == 200
    data = json.loads(body)
    assert data["response"] == "stub: hello"
    assert data["sources"] == []
    assert engine.queries == [("hello", [])]
    # No CORS wildcard
    assert headers.get("access-control-allow-origin", "") != "*"
    assert headers.get("x-content-type-options") == "nosniff"


# ── Host header / DNS rebinding ────────────────────────────────────────────


def test_ask_rejects_bad_host(rag_server):
    srv, _ = rag_server
    status, _, _ = _request(srv._port, "/ask", host="evil.com", body=_ask_body("x"))
    assert status == 421


# ── Origin header ──────────────────────────────────────────────────────────


def test_ask_rejects_bad_origin(rag_server):
    srv, _ = rag_server
    status, _, _ = _request(
        srv._port, "/ask", origin="http://evil.com", body=_ask_body("x")
    )
    assert status == 403


def test_ask_accepts_tauri_origin(rag_server):
    srv, _ = rag_server
    status, _, _ = _request(
        srv._port,
        "/ask",
        origin="http://tauri.localhost",
        body=_ask_body("hi"),
    )
    assert status == 200


# ── size / length limits ───────────────────────────────────────────────────


def test_ask_rejects_oversized_body(rag_server):
    """_MAX_BODY_BYTES is 64 KiB — anything larger must be refused."""
    srv, _ = rag_server
    oversized = b'{"query":"' + (b"x" * (70 * 1024)) + b'","history":[]}'
    status, _, _ = _request(srv._port, "/ask", body=oversized)
    assert status == 413


def test_ask_rejects_missing_content_length(rag_server):
    srv, _ = rag_server
    status, _, _ = _request(srv._port, "/ask", body=b"", content_length_override=0)
    assert status == 413  # content_len <= 0


def test_ask_rejects_long_query(rag_server):
    srv, _ = rag_server
    long_q = "a" * 2100  # cap is 2000
    status, _, body = _request(srv._port, "/ask", body=_ask_body(long_q))
    assert status == 400
    assert b"too long" in body.lower()


def test_ask_rejects_long_history(rag_server):
    srv, _ = rag_server
    history = [{"role": "user", "content": "hi"}] * 200  # cap is 100
    status, _, _ = _request(srv._port, "/ask", body=_ask_body("q", history))
    assert status == 400


def test_ask_rejects_empty_query(rag_server):
    srv, _ = rag_server
    status, _, _ = _request(srv._port, "/ask", body=_ask_body(""))
    assert status == 400


def test_ask_rejects_bad_json(rag_server):
    srv, _ = rag_server
    status, _, _ = _request(srv._port, "/ask", body=b"not json at all")
    assert status == 400


# ── routing ────────────────────────────────────────────────────────────────


def test_unknown_path_returns_404(rag_server):
    srv, _ = rag_server
    status, _, _ = _request(srv._port, "/other", body=b"{}")
    assert status == 404


# ── OPTIONS preflight ──────────────────────────────────────────────────────


def test_options_ok_with_allowed_origin(rag_server):
    srv, _ = rag_server
    status, headers, _ = _request(
        srv._port, "/ask", method="OPTIONS", origin="http://127.0.0.1:5173"
    )
    assert status == 204
    assert headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert headers.get("vary", "").lower() == "origin"


def test_options_rejects_bad_origin(rag_server):
    srv, _ = rag_server
    status, _, _ = _request(
        srv._port, "/ask", method="OPTIONS", origin="http://evil.com"
    )
    assert status == 403
