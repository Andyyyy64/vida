# homelife.ai

A personal AI system for monitoring, managing, and analyzing your daily life.

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
daemon (Python)          web (Node.js/Hono)        frontend (React)
  ├─ Camera capture        ├─ REST API               ├─ Timeline view
  ├─ Screen capture        ├─ SQLite read-only       ├─ Frame detail
  ├─ Audio capture         ├─ Media serving          ├─ Summary panel
  ├─ Window monitor        ├─ MJPEG proxy            ├─ Live feed
  ├─ Presence detection    └─ Static file serving    ├─ Dashboard
  ├─ LLM analysis                                    ├─ Search
  ├─ Multimodal embedding                            └─ Activity heatmap
  ├─ Summary generation
  ├─ Report generation
  ├─ Chat integration
  ├─ SQLite write
  ├─ sqlite-vec vector store
  └─ MJPEG live server (port 3002)
```

- Daemon writes to SQLite, web reads it (WAL mode for concurrency)
- Window monitor runs a persistent PowerShell process with its own SQLite connection
- Shared `data/` directory: frames/, screens/, audio/, life.db
- LLM provider is abstracted: Gemini or Claude, configured in life.toml
- Multimodal embedding via Gemini Embedding 2 (camera, screen, audio, text → unified vector space)
- sqlite-vec for vector storage and KNN cosine similarity search

## Key Paths

- `daemon/` — Python package (daemon, capture, analysis, LLM, embedding, storage)
- `daemon/cli.py` — CLI entry point
- `daemon/daemon.py` — Main observer loop
- `daemon/config.py` — Config loading from life.toml
- `daemon/embedding.py` — Multimodal embedder (Gemini Embedding 2) for frames, chat, summaries
- `daemon/activity.py` — ActivityManager: DB-backed activity normalization + meta-category mapping
- `daemon/analyzer.py` — Frame analysis and summary generation
- `daemon/report.py` — Daily report generation
- `daemon/llm/` — LLM provider abstraction (base, gemini, claude)
- `daemon/capture/` — Camera, screen (PowerShell/WSL2), audio (ALSA), window (Win32 P/Invoke)
- `daemon/analysis/` — Motion, scene, change detection, presence, transcription
- `daemon/storage/database.py` — SQLite schema, migrations, queries, sqlite-vec vector store
- `daemon/storage/models.py` — Frame, Event, Summary, Report, ChatMessage dataclasses
- `daemon/notify.py` — Discord/LINE webhook notifications
- `daemon/chat/` — Chat platform adapters (base, discord, manager)
- `web/server/` — Hono API server + routes
- `web/server/db.ts` — SQLite connection (better-sqlite3, read-only)
- `web/server/routes/stats.ts` — Stats, activities, app usage, date range endpoints
- `web/server/routes/activities.ts` — Activity mappings from DB (cached 60s)
- `web/src/` — React frontend
- `web/src/lib/activity.ts` — Shared activity colors, labels, dynamic meta-category mapping
- `web/src/components/Dashboard.tsx` — Dashboard with focus score, pie chart, app usage, sessions
- `web/src/components/DetailPanel.tsx` — Frame detail with images, audio, window info, metadata
- `life.toml` — Runtime config
- `.env` — API keys (GEMINI_API_KEY)
- `data/` — Runtime data (DB, frames, screens, audio)
- `docker-compose.yml` — Container orchestration

## Database Tables

- `frames` — Core capture data (path, screen, audio, transcription, analysis, activity, foreground_window)
- `window_events` — Focus change events (timestamp, process_name, window_title) for precise app duration tracking
- `activity_mappings` — Dynamic activity → meta_category mapping (seeded from existing frames, updated by LLM)
- `summaries` — Multi-scale summaries (10m, 30m, 1h, 6h, 12h, 24h)
- `events` — Scene changes, motion spikes, presence state changes
- `reports` — Daily auto-generated reports
- `memos` — Daily user memos (editable today only)
- `chat_messages` — Messages from chat platforms (Discord, etc.) with unified schema
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

**Config** (`life.toml`):
```toml
[embedding]
enabled = true
model = "gemini-embedding-2-preview"
dimensions = 3072  # native output; recommended: 768, 1536, 3072
```

## Conventions

- Python: dataclasses, type hints, logging module
- TypeScript: strict mode, Hono for API, Vite for build
- Database: SQLite with WAL mode, relative paths for media files
- Config: TOML for app config, .env for secrets
- Git commit prefixes: feat, fix, docs, refactor
- Do not git commit unless explicitly instructed by the user
