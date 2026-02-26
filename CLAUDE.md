# life.ai

A personal AI observer that automatically records daily life and enables reflection and pattern discovery.

## Project Direction

Two core values:

1. **Externalized memory** — Answer "what was I doing then?" Searchable, auto-generated diary.
2. **Productivity visibility** — Show "how focused was I?" and "where did my time go?" in numbers.

Improvement priorities:
1. Full-text search (across frame analyses and summaries)
2. Daily report auto-generation
3. Weekly/monthly stats dashboard
4. Improved activity classification accuracy
5. Mobile support / notification integration

## Architecture

```
daemon (Python)          web (Node.js/Hono)        frontend (React)
  ├─ Camera capture        ├─ REST API               ├─ Timeline view
  ├─ Screen capture        ├─ SQLite read-only       ├─ Frame detail
  ├─ Audio capture         ├─ Media serving          ├─ Summary panel
  ├─ LLM analysis          ├─ MJPEG proxy            ├─ Live feed
  ├─ Summary generation    └─ Static file serving    └─ Activity heatmap
  ├─ SQLite write
  └─ MJPEG live server (port 3002)
```

- daemon writes to SQLite, web reads it (WAL mode for concurrency)
- Shared `data/` directory: frames/, screens/, audio/, life.db
- LLM provider is abstracted: Gemini or Claude, configured in life.toml

## Key Paths

- `life/` — Python package (daemon, capture, analysis, LLM, storage)
- `life/cli.py` — CLI entry point
- `life/daemon.py` — Main observer loop
- `life/config.py` — Config loading from life.toml
- `life/llm/` — LLM provider abstraction (base, gemini, claude)
- `life/capture/` — Camera, screen (PowerShell/WSL2), audio (ALSA)
- `life/storage/database.py` — SQLite schema and queries
- `web/server/` — Hono API server + routes
- `web/server/db.ts` — SQLite connection (better-sqlite3, read-only)
- `web/src/` — React frontend
- `life.toml` — Runtime config
- `.env` — API keys (GEMINI_API_KEY)
- `data/` — Runtime data (DB, frames, screens, audio)
- `docker-compose.yml` — Container orchestration

## Conventions

- Python: dataclasses, type hints, logging module
- TypeScript: strict mode, Hono for API, Vite for build
- Database: SQLite with WAL mode, relative paths for media files
- Config: TOML for app config, .env for secrets
- Git commit prefixes: feat, fix, docs, refactor
- Do not git commit unless explicitly instructed by the user
