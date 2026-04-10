# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :x:                |

Security fixes are released against the current `0.2.x` line only.

## Local-Only Architecture

vida is designed as a **local-only** system. Captured data — camera frames, screenshots, audio recordings, transcriptions, analysis results, and the SQLite database — remains on the user's machine.

Outbound network traffic is limited to:

- **LLM provider APIs** (Google Gemini or Anthropic Claude) for frame analysis, summaries, and RAG. Captured images, audio, and text are sent only when the daemon is configured to use those providers. In `external` mode, the daemon broadcasts analysis requests to a local Claude Code instance over loopback WebSocket instead and performs no outbound LLM calls of its own.
- **Optional notification webhooks** for Discord / LINE. Webhook URLs are host-allowlisted (`discord.com`, `discordapp.com`, `canary.discord.com`, `ptb.discord.com`, `notify-api.line.me`) and must be `https://`.
- **Optional chat ingestion** (Discord) when enabled in settings.

No other network communication occurs during normal operation.

## Network Services

The daemon exposes three services, **all bound to `127.0.0.1` only**. They reject connections from non-loopback remotes, from requests whose `Host` header is not a loopback literal (DNS-rebinding defense), and from browser origins that are not the Tauri webview or `http://localhost:5173` (Vite dev):

| Port | Service       | Protocol  | Purpose                                          |
| ---- | ------------- | --------- | ------------------------------------------------ |
| 3002 | Live feed     | HTTP/MJPEG| Camera preview stream + `/health`                |
| 3003 | RAG           | HTTP/JSON | `POST /ask` for retrieval-augmented Q&A          |
| 3004 | WebSocket     | WS        | Event stream (frames, summaries, LLM errors, external-mode analysis requests) |

Request bodies are size-capped, query lengths and history sizes are bounded, and CORS wildcards are never emitted.

## Hardening

The following hardening is enforced as of 0.2.4:

**Daemon**

- All HTTP/WS servers bind to loopback only and validate `Host`, `Origin`, and the remote peer.
- WebSocket inbound messages are restricted to a narrow type whitelist.
- LLM error messages are scrubbed of API keys (`AIza…`, `sk-…`, `Bearer …`) before being broadcast.
- Screen capture passes the target path to PowerShell via `$env:VIDA_SCREEN_PATH` rather than string interpolation, closing a command-injection vector.
- The analyzer prompt JSON-escapes untrusted strings (window titles, transcription, chat messages) and includes an explicit "data is not instructions" system note to reduce prompt-injection surface.
- On POSIX, the data directory is created with `umask 077` and chmod'd to `700`; `life.db` and its WAL/SHM sidecars, plus the pid file, are chmod'd to `600`.
- FTS5 search queries are length-capped; the connection uses `busy_timeout=5000` to avoid lock-contention denial of service.

**Tauri backend (Rust)**

- `ask_rag` requires the RAG URL to be loopback-only, enforces connect/request timeouts, and caps query length and history size.
- `get_live_frame` and context file commands use a `safe_join` helper that rejects `..` and confirms the canonical path stays under `data_dir`.
- Python binary discovery canonicalizes every candidate and requires the `.venv` interpreter to resolve under the repo root.
- The bundled `devices.py` helper is refused if it does not canonicalize under the bundled daemon directory.
- `settings.put` allow-lists env keys, rejects newlines / NUL bytes, and caps values at 4 KiB.
- Every date parameter passes through a shared `validate_date` helper; summary scales are validated against the known interval set; export formats are whitelisted; memo content is capped at 64 KiB.

**Tauri config (webview)**

- Asset Protocol scope is empty at config time and dynamically registered at runtime to the real `data_dir`, so the webview cannot resolve files outside captured-data roots.
- CSP pins `img-src`, `media-src`, and `connect-src` to the specific loopback ports (3002/3003/3004) and to `localhost:5173` for Vite HMR; `script-src 'self'`, `object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'none'`.

**Frontend (React)**

- `RagChat` sanitizes `marked` output with DOMPurify using a strict tag/attribute allowlist and forces anchors to `target="_blank" rel="noopener noreferrer"`.
- i18next runs with `escapeValue: true`, and `dangerouslySetInnerHTML` is not used outside the sanitized RAG render path.

**Test coverage**

- `tests/e2e/` boots the real daemon servers on ephemeral loopback ports and asserts `Host` / `Origin` / body-size / query-length invariants against the live sockets.
- `web/e2e/` (Playwright) covers the frontend against a fake in-process runtime, including the DOMPurify sanitization path in `RagChat`.

## Reporting a Vulnerability

If you discover a security vulnerability in vida, please report it responsibly. **Do not open a public GitHub issue for security vulnerabilities.**

### How to Report

1. **GitHub Security Advisory** (preferred): Navigate to the repository's Security tab and create a private security advisory.
2. **Email**: Send a detailed report to the repository maintainer via the contact information listed on their GitHub profile.

### What to Include

- A clear description of the vulnerability
- Steps to reproduce the issue
- The potential impact
- Any suggested fixes, if applicable

### Response Timeline

- **Acknowledgment**: Within 48 hours of receiving the report
- **Initial assessment**: Within 7 days
- **Fix or mitigation**: Targeted within 30 days, depending on severity and complexity

### What to Expect

- You will receive confirmation that your report has been received.
- We will work with you to understand and validate the issue.
- A fix will be developed and tested before public disclosure.
- You will be credited in the release notes (unless you prefer to remain anonymous).

## Responsible Disclosure

We ask that you:

- Allow reasonable time for us to address the issue before any public disclosure.
- Avoid accessing or modifying other users' data.
- Act in good faith to avoid disruption to the project and its users.

## Security Best Practices for Users

- **API keys** are stored in the `settings` table of `life.db`. Keep `data/` off version control and do not share the database file. On POSIX the daemon already chmod's it to `600`; on Windows, restrict access via NTFS ACLs if the machine is shared.
- **Do not expose daemon ports** (3002/3003/3004) beyond loopback. Tunneling them over SSH or a VPN is fine, but do not bind them to `0.0.0.0` or put them behind a reverse proxy — the Host/Origin checks are loopback-only and will reject non-loopback traffic by design.
- **Review LLM provider** in Settings. Frames and audio leave the machine only when a cloud provider is configured. The `external` provider keeps all analysis on the local machine via Claude Code.
- **Review webhook URLs** before enabling Discord/LINE notifications — only the allowlisted hosts above will succeed.
- **Keep dependencies updated**. `pip-audit` runs in CI via `uv sync --dev`; for the frontend, run `npm audit` periodically.
- **Review capture settings** in the Settings UI to ensure they match your privacy preferences (camera/mic/screen enabled state, capture interval, sleep hours).
