# vida

> *vida* — Spanish for "life." A personal AI system for monitoring, managing, and analyzing your daily life.

## Project Direction

Three pillars:

1. **Monitoring** — Continuous, automatic recording (camera, screen, audio, app focus). No manual input.
2. **Management** — Externalized memory. Instantly answer "what was I doing then?" via search and timeline.
3. **Analysis** — Concrete productivity metrics. Focus scores, activity breakdowns, long-term patterns.

Improvement priorities:
1. Improved activity classification accuracy
2. Long-term trend analysis (weekly/monthly patterns)

## Architecture

```
daemon (Python)          tauri (Rust)              frontend (React)
  ├─ Camera capture        ├─ rusqlite queries        ├─ Timeline view
  ├─ Screen capture        ├─ IPC commands            ├─ Frame detail
  ├─ Audio capture         ├─ Asset Protocol          ├─ Summary panel
  ├─ Window monitor        ├─ System tray             ├─ Live feed
  ├─ Presence detection    ├─ Daemon lifecycle        ├─ Dashboard
  ├─ LLM analysis          └─ Auto venv setup         ├─ Search
  ├─ Multimodal embedding                             └─ Activity heatmap
  ├─ Summary generation
  ├─ Report generation
  ├─ Chat integration
  ├─ SQLite write
  ├─ sqlite-vec vector store
  ├─ MJPEG live server (port 3002)
  └─ WebSocket server (port 3004)
```

- **Tauri v2** desktop app — Rust core + OS WebView (no Chromium bundling)
- Frontend communicates via `invoke()` IPC, not HTTP fetch
- Media files served via Tauri Asset Protocol (`asset://`)
- Daemon writes to SQLite, Tauri reads it (WAL mode for concurrency)
- Window monitor runs a persistent PowerShell process with its own SQLite connection
- Shared `data/` directory: frames/, screens/, audio/, life.db
- Settings stored in SQLite `settings` table (not files)
- LLM provider: Gemini, Claude, or "external" (Claude Code via WebSocket) — configured in DB settings
- Multimodal embedding via Gemini Embedding 2 (camera, screen, audio, text → unified vector space)
- sqlite-vec for vector storage and KNN cosine similarity search

## Key Paths

- `daemon/` — Python package (daemon, capture, analysis, LLM, embedding, storage)
- `daemon/cli.py` — CLI entry point
- `daemon/daemon.py` — Main observer loop
- `daemon/config.py` — Config loading from DB (with life.toml fallback)
- `daemon/embedding.py` — Multimodal embedder (Gemini Embedding 2) for frames, chat, summaries
- `daemon/activity.py` — ActivityManager: DB-backed activity normalization + meta-category mapping
- `daemon/analyzer.py` — Frame analysis and summary generation
- `daemon/report.py` — Daily report generation
- `daemon/ws_server.py` — WebSocket server for Claude Code / UI bidirectional communication
- `daemon/llm/` — LLM provider abstraction (base, gemini, claude)
- `daemon/capture/` — Camera, screen (PowerShell/WSL2), audio (ALSA/sounddevice), window (Win32 P/Invoke)
- `daemon/analysis/` — Motion, scene, change detection, presence, transcription
- `daemon/storage/database.py` — SQLite schema, migrations, queries, sqlite-vec vector store
- `daemon/storage/models.py` — Frame, Event, Summary, Report, ChatMessage dataclasses
- `daemon/notify.py` — Discord/LINE webhook notifications
- `daemon/chat/` — Chat platform adapters (base, discord, manager)
- `web/src-tauri/` — Tauri v2 Rust backend
- `web/src-tauri/src/lib.rs` — App setup, path resolution, daemon spawn, tray
- `web/src-tauri/src/db.rs` — AppDb: SQLite connection, settings CRUD, activity mappings cache
- `web/src-tauri/src/commands/` — 18 IPC command modules (frames, stats, settings, etc.)
- `web/src-tauri/src/process.rs` — Daemon process lifecycle (spawn/stop)
- `web/src-tauri/src/python.rs` — Python discovery (.venv → python3 → python)
- `web/src-tauri/src/models.rs` — Serde structs for IPC
- `web/src-tauri/tauri.conf.json` — App config, bundle resources, window settings
- `web/src/` — React frontend
- `web/src/lib/api.ts` — IPC layer using `invoke()` for all API calls
- `web/src/lib/media.ts` — Asset Protocol URL helper (`convertFileSrc`)
- `web/src/lib/activity.ts` — Activity colors, labels, dynamic meta-category mapping
- `web/src/components/Dashboard.tsx` — Dashboard with focus score, pie chart, app usage, sessions
- `web/src/components/DetailPanel.tsx` — Frame detail with images, audio, window info, metadata
- `web/src/components/Settings.tsx` — Settings modal (reads/writes DB via IPC)
- `data/` — Runtime data (DB, frames, screens, audio)

## Database Tables

- `frames` — Core capture data (path, screen, audio, transcription, analysis, activity, foreground_window)
- `window_events` — Focus change events (timestamp, process_name, window_title) for precise app duration tracking
- `activity_mappings` — Dynamic activity → meta_category mapping (seeded from existing frames, updated by LLM)
- `summaries` — Multi-scale summaries (10m, 30m, 1h, 6h, 12h, 24h)
- `events` — Scene changes, motion spikes, presence state changes
- `reports` — Daily auto-generated reports
- `memos` — Daily user memos (editable today only)
- `chat_messages` — Messages from chat platforms (Discord, etc.) with unified schema
- `settings` — Key-value settings store (replaces life.toml + .env)
- `frames_fts` / `summaries_fts` — FTS5 trigram indexes for full-text search
- `vec_items` — sqlite-vec vec0 virtual table (float[3072] cosine distance, unified embedding store)
- `vec_items_meta` — Embedding metadata (item_type, source_id, timestamp, preview) joined to vec_items

## Embedding System

Gemini Embedding 2 (`gemini-embedding-2-preview`) maps all data types into a single 3072-dim vector space via sqlite-vec.

**Embedded content types:**
- `frame` — Multimodal: camera JPEG + screen PNG + audio WAV + text (description, activity, transcription, window)
- `chat` — Text: message content with platform/channel/author context
- `summary` — Text: summary content with time scale prefix

**Data flow:**
```
tick (30s) → LLM analysis → embed_frame (background thread)
           → check summaries → embed_summary (background thread)
           → check chat → embed_chat (background thread)
                               ↓
                    Gemini Embedding 2 API
                    (task_type=RETRIEVAL_DOCUMENT)
                               ↓
                    vec_items (sqlite-vec, cosine KNN)
                    vec_items_meta (type, source_id, timestamp, preview)
```

**Search:** `embed_text(query)` with `task_type=RETRIEVAL_QUERY` → `search_similar()` → cross-type KNN results

## Claude Code Integration

The daemon supports an "external" LLM provider mode where Claude Code handles all analysis via WebSocket + CLI.

**Architecture:**
```
Claude Code (terminal) ←── CLI commands ──→ daemon (Python)
         ↑                                       │
         └────── WebSocket (port 3004) ──────────┘
                                                  │
Tauri UI ←── WebSocket (port 3004) ──────────────┘
```

**External mode (`llm.provider = "external"`):**
- Daemon captures frames but skips LLM analysis
- Broadcasts `analyze_request` events via WebSocket
- Claude Code receives events, reads images, analyzes, sends results back via CLI
- Summaries, reports, and knowledge generation also delegated to Claude Code

**CLI data commands (JSON output):**
- `vida frames-list [DATE]` / `vida frames-get <ID>` / `vida frames-pending`
- `vida summary-list [DATE]` / `vida activity-stats` / `vida search <QUERY>`
- `vida frames-update <ID>` / `vida summary-create` / `vida memo-set`
- `vida connect --stream` / `vida watch --type <EVENT>`
- `vida status-json`

**Skills:** `.claude/skills/vida-*.md` teach Claude Code the analysis protocol.

## Conventions

- Python: dataclasses, type hints, logging module
- TypeScript: strict mode, Vite for build
- Rust: Tauri v2 commands, rusqlite for DB
- Database: SQLite with WAL mode, relative paths for media files
- Config: All settings in SQLite `settings` table
- Git commit prefixes: feat, fix, docs, refactor
- Do not git commit unless explicitly instructed by the user
