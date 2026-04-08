---
name: vida-connect
description: Use when the user asks to connect to vida, start analysis, or monitor their activity. This skill makes Claude Code act as vida's AI brain.
---

# vida Connect — Automatic Analysis Mode

You are connecting to vida, a personal life observer daemon. Your job is to act as its AI brain: analyze captured frames, classify activities, and generate summaries — automatically and continuously.

## Step 1: Verify daemon is running

```bash
vida status-json
```

Check the output:
- `"running": true` → proceed
- `"running": false` → tell the user to start the daemon first (`vida start` or launch the Tauri app)
- Note the `data_dir` — all image paths are relative to it

## Step 2: Process pending backlog

Before starting the live loop, clear any unanalyzed frames:

```bash
vida frames-pending --limit 10
```

For each pending frame, run the **Analysis Cycle** below. If there are many (>20), process the most recent 20 and skip older ones.

## Step 3: Live analysis loop

Enter a continuous loop. Repeat until the user tells you to stop:

```
┌─→ vida watch --type analyze_request --timeout 120
│   (blocks until next frame or timeout)
│
│   If timeout → run vida watch again (daemon may be idle)
│   If event received ↓
│
├─→ **Analysis Cycle** (see below)
│
├─→ Every 10 frames: check if summaries need generation (see vida-summarize skill)
│
└── Loop back to watch
```

## Analysis Cycle

For each frame that needs analysis:

### 1. Read the frame data

The `analyze_request` event contains:
```json
{
  "frame_id": 123,
  "image_paths": ["frames/2026-04-08/14-30-00.jpg", "screens/2026-04-08/14-30-00.png"],
  "data_dir": "/absolute/path/to/data",
  "transcription": "...",
  "foreground_window": "Code.exe|main.py - vida",
  "idle_seconds": 5,
  "has_face": true,
  "pose_data": "..."
}
```

### 2. Read the images

Use the Read tool to view the camera and screen images:
- Camera: `<data_dir>/<image_paths[0]>` — shows the user physically
- Screen: `<data_dir>/<image_paths[1]>` — shows what's on their monitor

### 3. Analyze

Look at both images together and determine:

**Description** (1-2 sentences, Japanese):
- What is the user doing right now?
- This is a continuous log — don't describe the person as a stranger each time
- Reference the transcription and foreground window for context

**Activity** (short Japanese category name):
- Use existing categories when possible (check with `vida activity-stats` on first run)
- Common: プログラミング, ブラウジング, 動画視聴, 休憩, 食事, 睡眠, 不在, チャット
- Only create new categories if nothing fits

**Meta-category** (exactly one of):
- `focus` — coding, studying, writing, deep work
- `communication` — chat, meetings, calls
- `entertainment` — videos, games, social media
- `browsing` — web browsing, research
- `break` — rest, eating, stretching
- `idle` — absent, sleeping, AFK

**Priority rule: physical state > screen content.**
If the user is lying down but screen shows code → `break`, not `focus`.
If `idle_seconds >= 300` → likely `idle` (absent/AFK).
If `has_face = false` and screen is idle → `idle`.

### 4. Send results

```bash
vida frames-update <frame_id> \
  --analysis "デスクでVS Codeを使ってTypeScriptのコードを書いている" \
  --activity "プログラミング" \
  --meta-category "focus"
```

Then immediately go back to watching for the next frame.

## Important Notes

- **Speed matters.** Each analysis should take seconds, not minutes. The daemon captures every 30s.
- **Don't ask the user** for each frame. This is autonomous. Just analyze and update.
- **Be consistent.** Use the same activity names across frames. Check existing categories first.
- **Errors are OK.** If you can't read an image or something fails, skip that frame and continue.
- **Summaries.** Every ~10 frames, check if 10m/30m/1h summaries need generation (see vida-summarize skill).
