# life.ai

A personal AI observer that automatically records your daily life and enables reflection and pattern discovery.

## Vision

**"Record your life, reflect on it, and see the patterns."**

Two core values:

1. **Externalized memory** — Instantly answer "what was I doing then?" Your day is recorded automatically, no journaling required.
2. **Productivity visibility** — See "how focused was I today?" and "where did my time go?" in concrete numbers.

## Features

- **30-second interval capture** — Automatically records webcam + PC screen + audio
- **Burst screen capture** — Takes 3 screenshots per interval (0s, 10s, 20s) to track temporal changes
- **AI analysis** — Gemini / Claude analyzes each frame and describes what you're doing
- **Activity classification** — Auto-categorizes activities (e.g. "Programming", "YouTube", "Browsing")
- **Multi-scale summaries** — Hierarchical activity summaries from 10min to 24h, generated automatically
- **Event detection** — Detects scene changes (light→dark) and motion spikes
- **Live feed** — MJPEG 10fps real-time video stream
- **Web UI** — Timeline view, frame details, burst screenshot switching, summary browsing

## Roadmap

- [ ] Full-text search — Search across frame analyses and summaries
- [ ] Daily report auto-generation — Automatic daily reflections delivered to you
- [ ] Weekly/monthly stats dashboard — Visualize long-term patterns
- [ ] Improved activity classification — Finer-grained, more accurate categorization
- [ ] Mobile support / notification integration — Reflection that fits into daily life

## Setup

### Requirements

- Python 3.12+
- Node.js 22+
- WSL2 (uses powershell.exe for screen capture)
- Gemini API key or Claude API key

### Installation

```bash
# Python
uv sync  # or pip install -e .

# Web UI
cd web && npm install
```

### Configuration

```bash
# Set API key in .env
echo "GEMINI_API_KEY=your-key-here" > .env

# Configure provider in life.toml (defaults used if omitted)
cat > life.toml << 'EOF'
[llm]
provider = "gemini"           # "gemini" or "claude"
gemini_model = "gemini-2.5-flash"

[capture]
interval_sec = 30
screen_burst_count = 3        # number of burst screenshots
EOF
```

Add user context to `data/context.md` so the AI can reference your name, environment, and habits in its analysis.

### Running

```bash
# Start daemon (background)
life start -d

# Start web UI
cd web && npm run dev
```

- Web UI: http://localhost:5173
- API: http://localhost:3001
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
| `life review [DATE] [--json]` | Generate review package |

## Configuration Options

All options in `life.toml`:

```toml
data_dir = "data"

[capture]
device = 0              # camera device ID
interval_sec = 30       # capture interval (seconds)
width = 640
height = 480
jpeg_quality = 85
screen_burst_count = 3  # burst screenshots per interval

[analysis]
motion_threshold = 0.02
brightness_dark = 40.0
brightness_bright = 180.0

[llm]
provider = "gemini"              # "gemini" or "claude"
claude_model = "haiku"
gemini_model = "gemini-2.5-flash"
```

## Web API

| Endpoint | Description |
|----------|-------------|
| `GET /api/frames?date=YYYY-MM-DD` | List frames for a date |
| `GET /api/frames/latest` | Get latest frame |
| `GET /api/frames/:id` | Get frame by ID |
| `GET /api/summaries?date=...&scale=...` | List summaries |
| `GET /api/events?date=...` | List events |
| `GET /api/stats?date=...` | Daily statistics |
| `GET /api/stats/activities?date=...` | Activity breakdown with duration |
| `GET /api/stats/dates` | List dates with data |
| `GET /media/{path}` | Serve image/audio files |

## Tech Stack

- **Backend**: Python 3.12 / Click / OpenCV / SQLite
- **LLM**: Google Gemini / Anthropic Claude (abstracted provider layer)
- **Frontend**: React 19 / TypeScript / Vite
- **Web Server**: Hono + better-sqlite3
- **Infra**: Docker Compose / WSL2 + powershell.exe (screen capture)
