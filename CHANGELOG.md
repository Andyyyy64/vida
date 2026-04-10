# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.5] - 2026-04-10

### Security

- Comprehensive security audit across daemon, Tauri backend, webview, and frontend:
  - MJPEG (3002), RAG (3003), and WebSocket (3004) servers bind to `127.0.0.1` only; reject non-loopback remotes, bad `Host` headers (DNS-rebinding defense), and untrusted browser origins. CORS wildcards dropped.
  - WebSocket inbound message types restricted to a narrow whitelist; Origin validated on handshake.
  - LLM error messages scrubbed of API keys (Gemini, OpenAI, Bearer) before being broadcast via WebSocket.
  - Screen capture passes the target path to PowerShell via `$env:VIDA_SCREEN_PATH` to close a command-injection vector.
  - Analyzer prompt JSON-escapes untrusted strings (window titles, transcription, chat) and carries an explicit "data is not instructions" system note to reduce prompt-injection surface.
  - Notification webhooks restricted to allowlisted Discord / LINE hosts over HTTPS.
  - POSIX data directory created with `umask 077` and chmod'd to `700`; `life.db` + WAL/SHM sidecars and the pid file chmod'd to `600`.
  - FTS5 search queries length-capped; SQLite connection `busy_timeout=5000`.
- Tauri backend hardening:
  - `ask_rag` validates RAG URL is loopback-only with connect/request timeouts and caps query/history sizes.
  - `safe_join` helper rejects `..` and confirms canonical paths stay under `data_dir`.
  - Python binary discovery canonicalizes every candidate and requires the `.venv` interpreter to resolve under repo root.
  - `devices.py` refused if it does not canonicalize under the bundled daemon directory.
  - `settings.put` allow-lists env keys, rejects newlines / NUL bytes, caps values at 4 KiB.
  - Every date-taking command validated via `validate_date`; summary scales validated against the known interval set; export formats whitelisted; memo content capped at 64 KiB.
- Tauri webview config:
  - `assetProtocol` scope empty at config time and dynamically registered at runtime to the real `data_dir`.
  - CSP pins `img/media/connect` to specific loopback ports (3002/3003/3004) + `localhost:5173` for Vite HMR; `script-src 'self'`, `object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'none'`.
- Frontend:
  - `RagChat` sanitizes `marked` output with DOMPurify using a strict tag/attribute allowlist; anchors forced to `target="_blank" rel="noopener noreferrer"`.
  - i18next `escapeValue: true`; `dangerouslySetInnerHTML` removed outside the sanitized RAG path.

### Added

- `tests/e2e/` — network-level integration tests that boot the real daemon servers (MJPEG, RAG, WebSocket) on ephemeral loopback ports and assert `Host` / `Origin` / body-size / query-length invariants (39 tests).
- `web/e2e/` — Playwright suite covering 26 frontend UI flows against an in-process fake runtime (timeline/detail, date nav, dashboard, search, RAG XSS sanitization, chat modal, summary panel, memo, settings, i18n, live feed, WebSocket events, onboarding, header clock, data modal).
- `SECURITY.md` rewritten with a Network Services table, full hardening inventory, and updated user best practices.
- Security sections added to `README.md` and `README.ja.md`.

## [0.2.4] - 2026-04-09

### Added

- WebSocket server (port 3004) for bidirectional real-time communication
- Claude Code integration: external analysis mode (`llm.provider = "external"`)
- CLI data commands: `frames-list`, `frames-get`, `frames-pending`, `summary-list`, `activity-stats`, `search`, `status-json`, `frames-update`, `summary-create`, `memo-set`
- CLI streaming commands: `connect --stream`, `watch --type <event>`
- Claude Code skills (`.claude/skills/vida-*.md`) for automatic analysis loop
- React WebSocket hook with auto-reconnect and real-time UI updates
- WebSocket connection indicator in UI
- `vida` CLI alias alongside existing `life` alias

## [0.2.3] - 2026-04-08

### Fixed

- Settings modal scroll not working (fieldset/scroll container separation)

## [0.2.2] - 2026-04-08

### Added

- Interactive web demo with Three.js virtual scene (deployed to Vercel)
- Runtime abstraction layer decoupling frontend from Tauri IPC
- Demo mode: read-only Settings/Onboarding, accelerated virtual clock, footer banner
- i18n localization with Japanese and English language support

## [0.2.0] - 2026-04-07

### Added

- Tauri v2 desktop application replacing Electron + Hono (93-96% smaller binaries)
- Settings stored in SQLite DB (`settings` table), replacing file-based `life.toml` / `.env`
- Auto virtual environment (venv) setup on first launch
- System tray with close-to-tray behavior
- Linux support (.deb, .AppImage)

### Changed

- Renamed project from "david" to "vida"
- Removed Node.js web server; all API communication via Tauri IPC commands
- Migrated frontend data fetching from HTTP fetch to Tauri `invoke()`

## [0.1.0] - 2026-03-04

### Added

- Camera, screen, and audio capture with change-detection based triggering
- Screen burst capture with activity classification
- Real-time MJPEG live feed (~10fps) on port 3002
- Audio capture with speech-to-text transcription (Gemini-based)
- Foreground window detection and app time tracking
- Presence detection with face detection and idle activity categories
- MediaPipe pose detection with live skeleton overlay
- LLM-powered frame analysis and multi-scale summary generation (10m to 24h)
- Abstracted LLM provider layer supporting both Claude and Gemini
- Activity category normalization with DB-driven dynamic meta-categories
- Full-text search with FTS5 trigram tokenizer
- Daily report generation pipeline
- Discord/LINE notification support for daily reports
- Knowledge profile generation from accumulated data
- Chat platform integration with Discord adapter and backfill
- Daily memo feature with auto-save and LLM context injection
- Web UI with React frontend: timeline view, frame detail, summary panel, live feed
- Dashboard with focus score, pie charts, app usage, and session timeline
- Date range stats API for weekly/monthly views
- Activity session calculation API
- Search with inline layout
- Mobile responsive design with panel switching
- Scroll-based frame navigation
- Detail panel redesign with sections and image modal
- Color-coded timeline dots with auto-polling
- Settings modal with device selection dropdowns
- Device enumeration API for camera and audio
- Electron desktop app wrapper with app icon and tray support
- WSL2 bridge mode for Windows native support
- Windows native support for all capture modules
- macOS support for all capture modules
- Cross-platform camera and audio device enumeration
- Docker Compose setup for daemon and web services
- GitHub Actions release workflow with first-run setup
- Standalone binary distribution bundling uv and daemon source
- Health endpoint with poll-based live feed status
- Japanese README and bilingual getting-started guide

### Changed

- Replaced Whisper with Gemini for audio transcription
- Replaced hardcoded activity aliases with fuzzy matching
- Replaced hardcoded activity categories with DB-driven dynamic system
- Improved activity classification accuracy (prioritize physical state over screen content)
- Improved live feed performance with expand modal
- Improved audio capture quality and reliability
- Renamed product from life.ai to homelife.ai
- Renamed life/ package to daemon/ for clarity
- Refined timeline dot ring styles
- Updated global CSS variables and styles
- Changed default Gemini model to gemini-3.1-flash-lite-preview

### Fixed

- Gemini response parsing for NoneType parts
- Gemini 2.5 thinking token filtering
- Custom seekable audio player replacing native controls
- Local timezone handling for dates with header clock
- Session timeline rendering in Dashboard
- Rich markup error in notify-test CLI output
- FrameViewer image loading and tab reset on frame switch
- Summary cascade prevention on daemon startup
- LiveFeed fallback and context-aware analysis
- Time context in summary prompts to prevent duration hallucination
- Screen capture encoding
- Electron-builder arch flag syntax
- App icon resized to 512x512 for electron-builder Mac builds
- Daemon process restart on unexpected stop
- Sounddevice device selection on Mac and Windows
