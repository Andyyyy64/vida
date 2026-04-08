---
name: vida-analyze
description: Use when manually analyzing a specific vida frame or batch of frames outside the automatic loop
---

# vida Manual Frame Analysis

For automatic analysis, use the **vida-connect** skill instead. This skill is for one-off or batch analysis.

## Analyze a single frame

```bash
# Get frame with image data
vida frames-get <frame_id> --include-image
```

The response includes `path_base64` and `screen_path_base64` (base64-encoded images). Or read the image files directly:

```bash
# Get the data directory
vida status-json
# → {"data_dir": "/path/to/data", ...}
```

Then use the Read tool on `<data_dir>/<frame.path>` and `<data_dir>/<frame.screen_path>`.

Analyze and update:

```bash
vida frames-update <frame_id> \
  --analysis "説明文" \
  --activity "カテゴリ名" \
  --meta-category "focus"
```

## Batch analyze pending frames

```bash
vida frames-pending --limit 20
```

Process each frame in order. See **vida-connect** skill for analysis rules (priority: physical state > screen, meta-categories, etc.).

## Re-analyze existing frames

To override a previous analysis:

```bash
vida frames-get <frame_id>
# Look at the current analysis
vida frames-update <frame_id> --analysis "新しい説明" --activity "新しいカテゴリ" --meta-category "break"
```
