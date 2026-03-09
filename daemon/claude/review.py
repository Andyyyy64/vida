from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from daemon.config import Config
from daemon.storage.database import Database
from daemon.summary.timeline import TimelineBuilder


class ReviewPackager:
    """Generates a review package for Claude Code to analyze the day."""

    def __init__(self, config: Config, db: Database):
        self._config = config
        self._db = db
        self._timeline = TimelineBuilder(db)

    def generate(self, d: date) -> dict:
        stats = self._timeline.get_day_stats(d)
        timeline_entries = self._timeline.build(d)
        keyframes = self._db.get_keyframes_for_date(d)
        events = self._db.get_events_for_date(d)
        summaries = self._db.get_summaries_for_date(d)

        frame_paths = []
        for f in keyframes:
            abs_path = self._config.data_dir / f.path
            if abs_path.exists():
                frame_paths.append(
                    {
                        "path": str(abs_path.resolve()),
                        "timestamp": f.timestamp.isoformat(),
                        "brightness": f.brightness,
                        "motion_score": f.motion_score,
                        "scene_type": f.scene_type.value,
                        "claude_description": f.claude_description,
                    }
                )

        return {
            "date": d.isoformat(),
            "stats": stats,
            "timeline": [{"time": e.time, "icon": e.icon, "description": e.description} for e in timeline_entries],
            "keyframes": frame_paths,
            "events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "type": e.event_type,
                    "description": e.description,
                }
                for e in events
            ],
            "summaries": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "scale": s.scale,
                    "content": s.content,
                    "frame_count": s.frame_count,
                }
                for s in summaries
            ],
        }

    def save_review(self, d: date) -> Path:
        package = self.generate(d)
        out_dir = self._config.data_dir / "reviews"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{d.isoformat()}.json"
        with open(out_path, "w") as f:
            json.dump(package, f, indent=2, ensure_ascii=False)
        return out_path

    def get_prompt(self, d: date) -> str:
        package = self.generate(d)

        frame_list = "\n".join(
            f"  - {f['timestamp']} bright={f['brightness']:.0f} motion={f['motion_score']:.3f} | {f['claude_description'][:60]}"
            for f in package["keyframes"]
        )
        summary_text = "\n".join(
            f"  [{s['scale']}] {s['timestamp']}: {s['content'][:100]}" for s in package["summaries"]
        )

        return f"""## Daily Life Review - {d.isoformat()}

### Stats
- Frames captured: {package["stats"]["total_frames"]}
- Claude analyzed: {package["stats"]["analyzed_frames"]}
- Events: {package["stats"]["total_events"]}
- Avg brightness: {package["stats"]["avg_brightness"]:.1f}

### Summaries
{summary_text or "  (none yet)"}

### Keyframes
{frame_list or "  (no frames)"}

キーフレーム画像を読んで、1日の生活を総合的に分析してください。
"""
