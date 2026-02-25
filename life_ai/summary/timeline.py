from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from life_ai.storage.database import Database
from life_ai.storage.models import SCALES


@dataclass
class TimelineEntry:
    time: str
    icon: str
    description: str


EVENT_ICONS = {
    "motion_spike": "🏃",
    "scene_change": "💡",
}

SCALE_ICONS = {
    "10m": "🕐",
    "30m": "🕑",
    "1h": "🕒",
    "6h": "🕕",
    "12h": "🕛",
    "24h": "📅",
}


class TimelineBuilder:
    def __init__(self, db: Database):
        self._db = db

    def build(self, d: date) -> list[TimelineEntry]:
        entries: list[TimelineEntry] = []

        # Add summaries
        summaries = self._db.get_summaries_for_date(d)
        for s in summaries:
            icon = SCALE_ICONS.get(s.scale, "📝")
            entries.append(TimelineEntry(
                time=s.timestamp.strftime("%H:%M"),
                icon=icon,
                description=f"[{s.scale}] {s.content[:120]}",
            ))

        # Add events
        events = self._db.get_events_for_date(d)
        for event in events:
            icon = EVENT_ICONS.get(event.event_type, "📌")
            entries.append(TimelineEntry(
                time=event.timestamp.strftime("%H:%M"),
                icon=icon,
                description=event.description,
            ))

        entries.sort(key=lambda e: e.time)
        return entries

    def get_day_stats(self, d: date) -> dict:
        frames = self._db.get_frames_for_date(d)
        events = self._db.get_events_for_date(d)
        summaries = self._db.get_summaries_for_date(d)

        avg_brightness = 0.0
        avg_motion = 0.0
        analyzed_count = 0
        if frames:
            avg_brightness = sum(f.brightness for f in frames) / len(frames)
            avg_motion = sum(f.motion_score for f in frames) / len(frames)
            analyzed_count = sum(1 for f in frames if f.claude_description)

        summary_counts = {}
        for s in summaries:
            summary_counts[s.scale] = summary_counts.get(s.scale, 0) + 1

        return {
            "date": d.isoformat(),
            "total_frames": len(frames),
            "analyzed_frames": analyzed_count,
            "total_events": len(events),
            "summary_counts": summary_counts,
            "avg_brightness": avg_brightness,
            "avg_motion": avg_motion,
        }
