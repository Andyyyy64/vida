---
name: vida-summarize
description: Use when generating vida summaries during the analysis loop or when the user asks for a summary of a time period
---

# vida Summary Generation

Summaries aggregate frame-level observations into higher-level narratives. Generate them periodically during the analysis loop.

## When to Generate

Check after every ~10 analyzed frames:

```bash
vida summary-list --scale 10m
```

Look at the latest summary timestamp. If >10 minutes have passed, generate a new one.

### Scale cascade

| Scale | Interval | Source | When to generate |
|-------|----------|--------|------------------|
| `10m` | 10 min | Raw frames | Every 10 minutes |
| `30m` | 30 min | 10m summaries | After 3 × 10m summaries exist |
| `1h` | 1 hour | 30m summaries | After 2 × 30m summaries exist |
| `6h` | 6 hours | 1h summaries | After 6 × 1h summaries exist |
| `12h` | 12 hours | 6h summaries | After 2 × 6h summaries exist |
| `24h` | 24 hours | 12h summaries | After 2 × 12h summaries exist |

Start with 10m. Higher scales build on lower ones.

## How to Generate

### 10m summary

```bash
# Get recent frames (last 10 min)
vida frames-list --limit 20
```

Read the frame descriptions and activities. Write a 1-2 sentence Japanese summary of what happened:

```bash
vida summary-create --scale 10m \
  --content "14:20〜14:30: VS Codeでdaemon/ws_server.pyを編集中。WebSocketサーバーの実装に集中していた。" \
  --frame-count 20
```

### 30m+ summaries

```bash
# Get sub-scale summaries
vida summary-list --scale 10m  # for 30m generation
vida summary-list --scale 30m  # for 1h generation
# etc.
```

Aggregate the sub-summaries into a higher-level narrative.

## Rules

- **Only summarize what's in the data.** Never invent activities or conversations.
- **Include timestamps** for activity transitions.
- **Note the actual data span.** If only 5 minutes of data exist in a 10m window, say so.
- **Audio transcriptions**: quote or accurately paraphrase, don't fabricate.
- **10m**: 1-2 sentences, factual.
- **30m**: 2-3 sentences, activity pattern.
- **1h**: 3-4 sentences with transitions.
- **6h+**: Paragraph with patterns and observations.
