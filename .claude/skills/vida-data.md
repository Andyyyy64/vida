---
name: vida-data
description: Reference for all vida CLI data commands — reading and writing frames, summaries, activities, and memos
---

# vida Data Commands Reference

All data commands output JSON. The daemon's SQLite database is at `<data_dir>/life.db`.

## Read Commands

### `vida status-json`
Daemon status, frame counts, latest frame, today's memo.
```bash
vida status-json
# → {"running": true, "pid": 1234, "frames_today": 48, "latest_frame": {...}, ...}
```

### `vida frames-list [DATE]`
List frames for a date (default: today).
```bash
vida frames-list                    # today
vida frames-list 2026-04-08         # specific date
vida frames-list --limit 10         # last 10
```

### `vida frames-get <ID>`
Get a single frame with full detail.
```bash
vida frames-get 1234
vida frames-get 1234 --include-image   # includes base64 image data
```

### `vida frames-pending`
List frames that haven't been analyzed yet.
```bash
vida frames-pending --limit 20
# → {"count": 5, "data_dir": "/path/to/data", "frames": [...]}
```

### `vida summary-list [DATE]`
List summaries for a date, optionally filtered by scale.
```bash
vida summary-list
vida summary-list --scale 1h
vida summary-list 2026-04-08 --scale 24h
```

### `vida activity-stats`
Activity statistics over a date range.
```bash
vida activity-stats --days 7
# → {"stats": [{"activity": "プログラミング", "frame_count": 120, ...}], "mappings": [...]}
```

### `vida search <QUERY>`
Full-text search across frame descriptions and summaries.
```bash
vida search "料理"
vida search "プログラミング" --type frames --limit 10
# --type: frames, summaries, all (default)
```

## Write Commands

### `vida frames-update <ID>`
Update frame analysis (used after analyzing a frame).
```bash
vida frames-update 1234 \
  --analysis "デスクでVS Codeを使ってコーディング中" \
  --activity "プログラミング" \
  --meta-category "focus"
```

**Meta categories:** `focus`, `communication`, `entertainment`, `browsing`, `break`, `idle`

### `vida summary-create`
Create a new summary.
```bash
vida summary-create \
  --scale 1h \
  --content "14:00-15:00の間、主にプログラミング作業に集中していた。VS Codeでの開発が中心。" \
  --frame-count 12
```

**Scales:** `10m`, `30m`, `1h`, `6h`, `12h`, `24h`

### `vida memo-set`
Set the daily memo.
```bash
vida memo-set --content "今日はvida の Claude Code 連携機能を実装する"
vida memo-set --date 2026-04-08 --content "..."
```

## Data Model

### Frame
| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `timestamp` | ISO8601 | Capture time |
| `path` | string | Camera image (relative to data_dir) |
| `screen_path` | string | Screen capture (relative) |
| `audio_path` | string | Audio recording (relative) |
| `transcription` | string | Speech-to-text result |
| `description` | string | LLM analysis description |
| `activity` | string | Activity category |
| `foreground_window` | string | `process_name|window_title` |
| `brightness` | float | Scene brightness (0-255) |
| `motion_score` | float | Motion detection score |
| `idle_seconds` | int | Seconds since last input |

### Summary
| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `timestamp` | ISO8601 | Generation time |
| `scale` | string | Time scale (10m/30m/1h/6h/12h/24h) |
| `content` | string | Summary text |
| `frame_count` | int | Frames covered |

### Activity Mappings
Each activity has a `meta_category`:
- **focus** — coding, studying, writing, deep work
- **communication** — chat, meetings, calls
- **entertainment** — YouTube, games, social media
- **browsing** — web browsing, research
- **break** — rest, eating, stretching
- **idle** — absent, sleeping, AFK
