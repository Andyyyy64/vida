# homelife.ai

**English** | [日本語](README.ja.md)

A personal AI system for monitoring, managing, and analyzing your daily life.

## Vision

**"Monitor, manage, and analyze your life."**

Three pillars:

1. **Monitoring** — Continuous, automatic recording of your day. Camera, screen, audio, and app focus — all captured without any manual input.
2. **Management** — Instantly answer "what was I doing then?" An externalized, searchable memory that replaces journaling.
3. **Analysis** — See "how focused was I?" and "where did my time go?" in concrete patterns — daily, weekly, and monthly.

## Features

### Capture & Sensing

- **Interval capture** — Webcam + screen + audio captured every 30 seconds (configurable). Between ticks, change detection checks every 1 second and saves extra frames/screenshots when significant visual changes occur (screen: 10% threshold, camera: 15% perceptual hash difference).
- **Foreground window tracking** — Persistent PowerShell process monitors app focus changes every 500ms via Win32 P/Invoke (`GetForegroundWindow`), recording process name and window title for precise per-app duration tracking.
- **Presence detection** — Haar cascade face detection + MOG2 motion analysis with hysteresis state machine (present → absent → sleeping). Requires 3 consecutive ticks without face before transitioning. Sleep state detected by low brightness during configured night hours.
- **Audio capture & transcription** — ALSA recording with auto-device detection. Silence trimming (500 amplitude threshold, min 0.3s voice) keeps only meaningful audio. Transcription via LLM with user context awareness.
- **Live feed** — MJPEG streaming server on port 3002 at ~30fps, independent of the main capture interval.

### AI Analysis

- **Frame analysis** — Each tick sends camera image + screen capture + audio + foreground window info to LLM (Gemini or Claude). Returns structured JSON with activity category and natural language description.
- **Activity classification** — LLM freely generates activity category names. Existing categories are shown as examples for consistency, and new categories are accepted and registered automatically. Fuzzy matching (LCS similarity ≥ 0.7) normalizes variants to existing categories. All activity → meta-category mappings are stored in the `activity_mappings` DB table.
- **Meta-categories** — Activities are dynamically mapped to 6 meta-categories for productivity scoring: **focus**, **communication**, **entertainment**, **browsing**, **break**, **idle**. The LLM outputs the meta-category alongside each activity. The mapping is stored in DB and served to the frontend via API.
- **Multi-scale summaries** — Hierarchical generation: 10m (from raw frames) → 30m → 1h → 6h → 12h → 24h (includes keyframe images + transcriptions + improvement suggestions). Each scale builds from the one below.
- **Daily reports** — Auto-generated on day change. Includes activity breakdown, timeline narrative, focus percentage (focus frames / active frames), and event list. Delivered via webhook.
- **Context awareness** — User profile (`data/context.md`) and recent 5-frame history included in every LLM prompt for continuity.

### Web UI

- **Timeline** — Frames grouped by hour, sized by motion score, colored by activity meta-category. Keyboard navigation (arrow keys) and scroll-wheel frame switching.
- **Detail panel** — Camera image (click to expand), screen captures (main + change-detected extras with thumbnail strip), audio player with transcription, foreground window info, and all metadata.
- **Summary panel** — Browse summaries by scale (10m–24h) with expand/collapse. Click a summary to highlight its time range on the timeline.
- **Dashboard** — Focus score %, pie chart by meta-category, activity list with duration bars, top 10 app usage with switch counts, weekly stacked bar chart, gantt-style session timeline.
- **Search** — FTS5 trigram full-text search across frame descriptions, transcriptions, activities, window titles, and summaries. Click results to jump to date/frame.
- **Activity heatmap** — Frames-per-hour intensity visualization across 24 hours.
- **Live feed** — Real-time MJPEG stream with LIVE/OFFLINE indicator, expandable to full-screen modal.
- **Mobile** — Responsive layout with tab switching (Summaries / Timeline / Detail) on narrow viewports.
- **Auto-refresh** — 30-second polling for new frames, summaries, and events when viewing today's data.

### Chat Platform Integration

Collects conversations from external chat platforms to enrich the "externalized memory." Knowing what you were discussing — and with whom — adds a critical dimension to daily activity tracking.

**Architecture:** Adapter pattern with a unified `ChatSource` interface. Each platform has its own adapter; users enable only what they use via `life.toml`.

| Platform | Status | Method | DMs | Servers/Groups |
|----------|--------|--------|-----|-----------------|
| **Discord** | Implemented | REST API polling (user token) | Yes | Yes |
| **LINE** | Planned | Chat export import | Yes | Yes |
| **Slack** | Planned | Bot token + Events API | — | Yes |
| **Telegram** | Planned | Bot API / TDLib | Yes | Yes |
| **WhatsApp** | Planned | Chat export import | Yes | Yes |
| **Teams** | Planned | Microsoft Graph API | Yes | Yes |

**How it works:**
1. Platform adapter polls for new messages in a background thread
2. Messages are stored in `chat_messages` table with unified schema (platform, channel, author, content, timestamp)
3. Recent conversations are injected into LLM prompts — frame analysis sees "user was discussing X on Discord" alongside screen/camera data
4. Daily reports include a chat activity summary (message counts per channel)

**Discord specifics:** Uses a user token for full access (servers + DMs + group DMs). On first run, backfills past N months of history (`backfill_months`, default 3) by paginating backwards through all channels. Thereafter, polls every 60s (configurable) for new messages, comparing `last_message_id` per channel to fetch only deltas. Handles rate limiting with automatic retry.

### Notifications

- **Discord** — Daily reports via webhook embed (4000 char limit, purple accent)
- **LINE Notify** — Daily reports via LINE API (1000 char limit)
- Test with `life notify-test`

## Architecture

```
daemon/ (Python)         web/ (Node.js/Hono)       frontend (React)
  ├─ Camera capture        ├─ REST API               ├─ Timeline view
  ├─ Screen capture        ├─ SQLite read-only       ├─ Frame detail
  ├─ Audio capture         ├─ Media serving          ├─ Summary panel
  ├─ Window monitor        ├─ MJPEG proxy            ├─ Live feed
  ├─ Presence detection    └─ Static file serving    ├─ Dashboard
  ├─ LLM analysis                                    ├─ Search
  ├─ Summary generation                              ├─ Activity heatmap
  ├─ Report generation                               └─ Mobile responsive
  ├─ Chat integration
  ├─ Change detection
  ├─ SQLite write
  └─ MJPEG live server (port 3002)
```

- Daemon writes to SQLite, web reads it (WAL mode for concurrent access)
- Window monitor runs a persistent PowerShell process with its own SQLite connection
- Shared `data/` directory: `frames/`, `screens/`, `audio/`, `life.db`
- LLM provider abstracted: Gemini or Claude, configured in `life.toml`

### Threading model

| Thread | Purpose | Rate |
|--------|---------|------|
| Main loop | Capture + analysis + summaries | Every 30s (configurable) |
| Live feed | Webcam → MJPEG stream | ~30fps |
| Audio recording | ALSA capture during interval | Per tick |
| Window monitor | PowerShell → `window_events` table | 500ms polls |
| Change detection | Screen/camera hash comparison | Every 1s between ticks |
| Chat poller | Discord/etc → `chat_messages` table | Every 60s (configurable) |
| Live HTTP server | Serve MJPEG to clients | On demand |

## Project Structure

```
daemon/                  # Python package
  ├─ cli.py              # CLI entry point (Click)
  ├─ daemon.py           # Main observer loop
  ├─ config.py           # TOML config loading
  ├─ analyzer.py         # Frame analysis + summary generation
  ├─ activity.py         # ActivityManager: DB-backed normalization + meta-category mapping
  ├─ report.py           # Daily report generation
  ├─ notify.py           # Discord / LINE webhook notifications
  ├─ live.py             # MJPEG streaming server
  ├─ chat/               # Chat platform integration
  │   ├─ base.py         # Abstract ChatSource interface
  │   ├─ discord.py      # Discord adapter (user token, REST polling)
  │   └─ manager.py      # ChatManager: orchestrates adapters
  ├─ llm/                # LLM provider abstraction
  │   ├─ base.py         # Abstract base class
  │   ├─ gemini.py       # Google Gemini (image + audio support)
  │   └─ claude.py       # Anthropic Claude (via CLI)
  ├─ capture/            # Data capture modules
  │   ├─ camera.py       # Webcam (V4L2 / MJPEG)
  │   ├─ screen.py       # Screen capture (PowerShell)
  │   ├─ audio.py        # Audio recording (ALSA)
  │   ├─ window.py       # Foreground window monitor (PowerShell + Win32)
  │   └─ frame_store.py  # JPEG file storage
  ├─ analysis/           # Local analysis (no LLM)
  │   ├─ motion.py       # MOG2 background subtraction
  │   ├─ scene.py        # Brightness classification
  │   ├─ change.py       # Perceptual hash change detection
  │   ├─ presence.py     # Face detection + state machine
  │   └─ transcribe.py   # Audio → text via LLM
  ├─ summary/            # Summary formatting
  │   ├─ formatter.py    # CLI output formatting
  │   └─ timeline.py     # Timeline data builder
  ├─ claude/             # Claude-specific features
  │   ├─ analyzer.py     # Review analysis
  │   └─ review.py       # Daily review package generator
  └─ storage/            # Database layer
      ├─ database.py     # SQLite schema, migrations, queries
      └─ models.py       # Frame, Event, Summary, Report dataclasses

web/                     # Node.js web application
  ├─ server/
  │   ├─ index.ts        # Hono app setup, media serving
  │   ├─ db.ts           # SQLite connection (read-only)
  │   └─ routes/         # API route handlers
  └─ src/
      ├─ App.tsx         # Main SPA orchestrator
      ├─ components/     # React components
      ├─ hooks/          # Data fetching with 30s polling
      └─ lib/            # API client, types, activity module, utilities

data/                    # Runtime data (gitignored)
  ├─ frames/             # Camera JPEGs (YYYY-MM-DD/*.jpg)
  ├─ screens/            # Screen PNGs (YYYY-MM-DD/*.png)
  ├─ audio/              # Audio WAVs (YYYY-MM-DD/*.wav)
  ├─ live/               # Current MJPEG stream frame
  ├─ context.md          # User profile for LLM context
  ├─ life.db             # SQLite database (WAL mode)
  └─ life.pid            # Daemon PID file
```

## Setup

See **[getting-started.md](getting-started.md)** for full platform-specific instructions ([日本語版](getting-started.ja.md)).

| Platform | Guide |
|---|---|
| Windows (Native) | [getting-started.md#windows-native](getting-started.md#windows-native) |
| Windows (WSL2) | [getting-started.md#windows-wsl2](getting-started.md#windows-wsl2) |
| Mac | [getting-started.md#mac](getting-started.md#mac) |

### Requirements

| | Windows (Native) | Windows (WSL2) | Mac |
|---|---|---|---|
| Python | 3.12+ (Windows) | 3.12+ (in WSL2) | 3.12+ |
| Node.js | 22+ (Windows) | 22+ (in WSL2) | 22+ |
| Camera | Built-in / USB (DirectShow) | External USB via usbipd | Built-in |
| Microphone | Built-in / USB (WASAPI) | External USB via usbipd | Built-in |
| Screen capture | PowerShell + Windows Forms | PowerShell + Windows Forms | `screencapture` (built-in) |
| Window tracking | PowerShell + Win32 API | PowerShell + Win32 API | `osascript` (built-in) |
| Gemini API key | Required | Required | Required |

### Quick Start

```bash
uv sync
cd web && npm install && cd ..
echo "GEMINI_API_KEY=your-key-here" > .env

# Desktop app (recommended)
cd web && npm run electron:start

# Or browser mode
./start.sh
```

### Configuration

Configure in `life.toml` (all options in the [Configuration section](#configuration-1) below):

```toml
[llm]
provider = "gemini"
gemini_model = "gemini-2.5-flash"

[capture]
interval_sec = 30

[presence]
enabled = true
```

Add user context to `data/context.md` so the AI can reference your name, environment, and habits in its analysis.

### Running

```bash
./start.sh       # Start daemon + web UI together

life start       # Daemon only (foreground)
life start -d    # Daemon only (background)
cd web && npm run dev    # Web UI (dev mode)
```

- Web UI: http://localhost:3001
- Live feed: http://localhost:3002

### Docker

```bash
docker compose up
```

For environments with camera/audio devices, configure device mounts in `docker-compose.override.yml`.

## CLI Commands

| Command | Description |
|---------|-------------|
| `life start [-d]` | Start the observer daemon (`-d` for background) |
| `life stop` | Stop the running daemon |
| `life status` | Show status (frame count, summaries, disk usage) |
| `life capture` | Capture a single test frame |
| `life look` | Capture and analyze a frame immediately |
| `life recent [-n 5]` | Show recent frame analyses |
| `life today [DATE]` | Show timeline for the day |
| `life stats [DATE]` | Show daily statistics |
| `life summaries [DATE] [--scale 1h]` | Show summaries (10m/30m/1h/6h/12h/24h) |
| `life events [DATE]` | List detected events |
| `life report [DATE]` | Generate daily diary report |
| `life review [DATE] [--json]` | Generate review package |
| `life notify-test` | Test webhook notification |

## Configuration

All options in `life.toml`:

```toml
data_dir = "data"

[capture]
device = 0              # camera device ID (/dev/videoN)
interval_sec = 30       # capture interval (seconds)
width = 640
height = 480
jpeg_quality = 85
audio_device = ""       # ALSA device (empty = auto-detect)
audio_sample_rate = 44100

[analysis]
motion_threshold = 0.02    # MOG2 foreground pixel ratio
brightness_dark = 40.0     # below = DARK scene
brightness_bright = 180.0  # above = BRIGHT scene

[llm]
provider = "gemini"              # "gemini" or "claude"
claude_model = "haiku"
gemini_model = "gemini-2.5-flash"

[presence]
enabled = true
absent_threshold_ticks = 3       # ticks before absent state
sleep_start_hour = 23
sleep_end_hour = 8

[notify]
provider = "discord"             # "discord" or "line"
webhook_url = ""
enabled = false

[chat]
enabled = false                  # master switch for chat integration

[chat.discord]
enabled = false
user_token = ""                  # Discord user token
user_id = ""                     # Your Discord user ID
poll_interval = 60               # seconds between polls
backfill_months = 3              # fetch past N months on first run (0 = skip)
```

## Web API

| Endpoint | Description |
|----------|-------------|
| `GET /api/frames?date=YYYY-MM-DD` | List frames for a date |
| `GET /api/frames/latest` | Get latest frame |
| `GET /api/frames/:id` | Get frame by ID |
| `GET /api/summaries?date=...&scale=...` | List summaries |
| `GET /api/events?date=...` | List events |
| `GET /api/stats?date=...` | Daily statistics (counts, averages, hourly activity) |
| `GET /api/stats/activities?date=...` | Activity breakdown with duration and hourly detail |
| `GET /api/stats/apps?date=...` | App usage from window events (duration, switch count) |
| `GET /api/stats/dates` | List dates with data |
| `GET /api/stats/range?from=...&to=...` | Per-day stats with meta-category breakdown |
| `GET /api/sessions?date=...` | Activity sessions (consecutive frame grouping) |
| `GET /api/reports?date=...` | Get daily report |
| `GET /api/reports` | List recent reports |
| `GET /api/activities` | List activity categories with meta-categories |
| `GET /api/activities/mappings` | Activity → meta-category mapping table |
| `GET /api/search?q=...&from=...&to=...` | Full-text search (frames + summaries) |
| `GET /api/live/stream` | MJPEG stream proxy |
| `GET /api/live/frame` | Single JPEG snapshot |
| `GET /media/{path}` | Serve image/audio files |

## Database Schema

### frames
Core capture data: timestamp, camera path, screen path, extra screen paths, audio path, transcription, brightness, motion score, scene type, LLM description, activity category, foreground window.

### window_events
Focus change events recorded by the window monitor: timestamp, process name, window title. Used for precise app usage duration calculation via `LEAD()` window function.

### summaries
Multi-scale summaries (10m to 24h) with timestamp, scale, content, and frame count.

### events
Detected events: scene changes, motion spikes, presence state changes. Linked to source frame.

### activity_mappings
Dynamic activity → meta-category mapping. Primary key is activity name, with meta_category, first_seen timestamp, and frame_count. Seeded from existing frame data on first migration. Updated automatically as the LLM generates new activities.

### reports
Daily auto-generated reports with content, frame count, and focus percentage.

### chat_messages
Messages collected from chat platforms: platform, platform-specific message ID, channel/guild info, author, is_self flag, content, timestamp, and JSON metadata for attachments/embeds. Unique constraint on (platform, platform_message_id).

### memos
Daily user memos: date (primary key), content, updated_at. Editable only for today, read-only for past dates.

### FTS indexes
`frames_fts` (trigram) over description, transcription, activity, foreground_window. `summaries_fts` (trigram) over content.

## Tech Stack

- **Daemon**: Python 3.12 / Click / OpenCV / SQLite (WAL mode)
- **LLM**: Google Gemini (image + audio) / Anthropic Claude (via CLI)
- **Window tracking**: PowerShell / Win32 P/Invoke (`GetForegroundWindow`)
- **Web server**: Hono 4 / better-sqlite3 / Node.js 22
- **Frontend**: React 19 / TypeScript / Vite 6
- **Infra**: Docker Compose / WSL2
