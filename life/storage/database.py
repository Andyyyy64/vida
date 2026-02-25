from __future__ import annotations

import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path

from .models import Frame, Event, Summary, SceneType

SCHEMA = """
CREATE TABLE IF NOT EXISTS frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    path TEXT NOT NULL,
    screen_path TEXT DEFAULT '',
    audio_path TEXT DEFAULT '',
    transcription TEXT DEFAULT '',
    brightness REAL DEFAULT 0,
    motion_score REAL DEFAULT 0,
    scene_type TEXT DEFAULT 'normal',
    claude_description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    frame_id INTEGER REFERENCES frames(id)
);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    scale TEXT NOT NULL,
    content TEXT DEFAULT '',
    frame_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_frames_timestamp ON frames(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_summaries_timestamp ON summaries(timestamp);
CREATE INDEX IF NOT EXISTS idx_summaries_scale ON summaries(scale);
"""

MIGRATE_CLAUDE_DESC = """
ALTER TABLE frames ADD COLUMN claude_description TEXT DEFAULT '';
"""

MIGRATE_SUMMARIES = """
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    scale TEXT NOT NULL,
    content TEXT DEFAULT '',
    frame_count INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_summaries_timestamp ON summaries(timestamp);
CREATE INDEX IF NOT EXISTS idx_summaries_scale ON summaries(scale);
"""


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self):
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(frames)").fetchall()}
        if "claude_description" not in cols:
            self._conn.execute(MIGRATE_CLAUDE_DESC)
            self._conn.commit()
        if "screen_path" not in cols:
            self._conn.execute("ALTER TABLE frames ADD COLUMN screen_path TEXT DEFAULT ''")
            self._conn.commit()
        if "audio_path" not in cols:
            self._conn.execute("ALTER TABLE frames ADD COLUMN audio_path TEXT DEFAULT ''")
            self._conn.commit()
        if "transcription" not in cols:
            self._conn.execute("ALTER TABLE frames ADD COLUMN transcription TEXT DEFAULT ''")
            self._conn.commit()
        # Ensure summaries table exists
        self._conn.executescript(MIGRATE_SUMMARIES)

    def close(self):
        self._conn.close()

    # --- Frames ---

    def insert_frame(self, frame: Frame) -> int:
        cur = self._conn.execute(
            """INSERT INTO frames (timestamp, path, screen_path, audio_path, transcription,
               brightness, motion_score, scene_type, claude_description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                frame.timestamp.isoformat(),
                frame.path,
                frame.screen_path,
                frame.audio_path,
                frame.transcription,
                frame.brightness,
                frame.motion_score,
                frame.scene_type.value,
                frame.claude_description,
            ),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def update_frame_description(self, frame_id: int, description: str):
        self._conn.execute(
            "UPDATE frames SET claude_description=? WHERE id=?",
            (description, frame_id),
        )
        self._conn.commit()

    def get_frames_for_date(self, d: date) -> list[Frame]:
        start = datetime(d.year, d.month, d.day).isoformat()
        end = datetime(d.year, d.month, d.day, 23, 59, 59).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM frames WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (start, end),
        ).fetchall()
        return [self._row_to_frame(r) for r in rows]

    def get_frames_since(self, since: datetime) -> list[Frame]:
        rows = self._conn.execute(
            "SELECT * FROM frames WHERE timestamp >= ? ORDER BY timestamp",
            (since.isoformat(),),
        ).fetchall()
        return [self._row_to_frame(r) for r in rows]

    def get_frame_count_for_date(self, d: date) -> int:
        start = datetime(d.year, d.month, d.day).isoformat()
        end = datetime(d.year, d.month, d.day, 23, 59, 59).isoformat()
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM frames WHERE timestamp BETWEEN ? AND ?",
            (start, end),
        ).fetchone()
        return row["cnt"]

    def get_latest_frame(self) -> Frame | None:
        row = self._conn.execute(
            "SELECT * FROM frames ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return self._row_to_frame(row) if row else None

    # --- Events ---

    def insert_event(self, event: Event) -> int:
        cur = self._conn.execute(
            """INSERT INTO events (timestamp, event_type, description, frame_id)
               VALUES (?, ?, ?, ?)""",
            (
                event.timestamp.isoformat(),
                event.event_type,
                event.description,
                event.frame_id,
            ),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_events_for_date(self, d: date) -> list[Event]:
        start = datetime(d.year, d.month, d.day).isoformat()
        end = datetime(d.year, d.month, d.day, 23, 59, 59).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM events WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (start, end),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    # --- Summaries ---

    def insert_summary(self, summary: Summary) -> int:
        cur = self._conn.execute(
            """INSERT INTO summaries (timestamp, scale, content, frame_count)
               VALUES (?, ?, ?, ?)""",
            (
                summary.timestamp.isoformat(),
                summary.scale,
                summary.content,
                summary.frame_count,
            ),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_summaries_for_date(self, d: date, scale: str | None = None) -> list[Summary]:
        start = datetime(d.year, d.month, d.day).isoformat()
        end = datetime(d.year, d.month, d.day, 23, 59, 59).isoformat()
        if scale:
            rows = self._conn.execute(
                "SELECT * FROM summaries WHERE timestamp BETWEEN ? AND ? AND scale=? ORDER BY timestamp",
                (start, end, scale),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM summaries WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
                (start, end),
            ).fetchall()
        return [self._row_to_summary(r) for r in rows]

    def get_latest_summary(self, scale: str) -> Summary | None:
        row = self._conn.execute(
            "SELECT * FROM summaries WHERE scale=? ORDER BY timestamp DESC LIMIT 1",
            (scale,),
        ).fetchone()
        return self._row_to_summary(row) if row else None

    def get_summaries_since(self, since: datetime, scale: str) -> list[Summary]:
        rows = self._conn.execute(
            "SELECT * FROM summaries WHERE timestamp >= ? AND scale=? ORDER BY timestamp",
            (since.isoformat(), scale),
        ).fetchall()
        return [self._row_to_summary(r) for r in rows]

    # --- Keyframes ---

    def get_keyframes_for_date(self, d: date, max_frames: int = 20) -> list[Frame]:
        frames = self.get_frames_for_date(d)
        if len(frames) <= max_frames:
            return frames

        selected: list[Frame] = [frames[0]]

        # High-motion frames
        by_motion = sorted(frames[1:-1], key=lambda f: f.motion_score, reverse=True)
        for f in by_motion[: max_frames // 3]:
            if f not in selected:
                selected.append(f)

        # Evenly spaced
        step = max(1, len(frames) // (max_frames - len(selected)))
        for i in range(0, len(frames), step):
            if len(selected) >= max_frames - 1:
                break
            if frames[i] not in selected:
                selected.append(frames[i])

        selected.append(frames[-1])
        selected.sort(key=lambda f: f.timestamp)
        return selected[:max_frames]

    # --- Row converters ---

    @staticmethod
    def _row_to_frame(row: sqlite3.Row) -> Frame:
        return Frame(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            path=row["path"],
            screen_path=row["screen_path"] or "",
            audio_path=row["audio_path"] or "",
            transcription=row["transcription"] or "",
            brightness=row["brightness"],
            motion_score=row["motion_score"],
            scene_type=SceneType(row["scene_type"]),
            claude_description=row["claude_description"] or "",
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_type=row["event_type"],
            description=row["description"],
            frame_id=row["frame_id"],
        )

    @staticmethod
    def _row_to_summary(row: sqlite3.Row) -> Summary:
        return Summary(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            scale=row["scale"],
            content=row["content"],
            frame_count=row["frame_count"],
        )
