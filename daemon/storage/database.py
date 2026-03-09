from __future__ import annotations

import contextlib
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import ChatMessage, Event, Frame, Report, SceneType, Summary

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
    claude_description TEXT DEFAULT '',
    activity TEXT DEFAULT '',
    screen_extra_paths TEXT DEFAULT ''
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

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    content TEXT DEFAULT '',
    generated_at TEXT NOT NULL,
    frame_count INTEGER DEFAULT 0,
    focus_pct REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_frames_timestamp ON frames(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_summaries_timestamp ON summaries(timestamp);
CREATE INDEX IF NOT EXISTS idx_summaries_scale ON summaries(scale);
"""

MIGRATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS frames_fts USING fts5(
    claude_description, transcription, activity, foreground_window,
    content='frames', content_rowid='id',
    tokenize='trigram'
);

CREATE VIRTUAL TABLE IF NOT EXISTS summaries_fts USING fts5(
    content,
    content='summaries', content_rowid='id',
    tokenize='trigram'
);
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
        self._conn = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES, timeout=10)
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
        if "activity" not in cols:
            self._conn.execute("ALTER TABLE frames ADD COLUMN activity TEXT DEFAULT ''")
            self._conn.commit()
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_frames_activity ON frames(activity)")
        self._conn.commit()
        if "screen_extra_paths" not in cols:
            self._conn.execute("ALTER TABLE frames ADD COLUMN screen_extra_paths TEXT DEFAULT ''")
            self._conn.commit()
        if "foreground_window" not in cols:
            self._conn.execute("ALTER TABLE frames ADD COLUMN foreground_window TEXT DEFAULT ''")
            self._conn.commit()
        if "pose_data" not in cols:
            self._conn.execute("ALTER TABLE frames ADD COLUMN pose_data TEXT DEFAULT ''")
            self._conn.commit()
        # Ensure summaries table exists
        self._conn.executescript(MIGRATE_SUMMARIES)
        # Window events table for precise app usage tracking
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS window_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                process_name TEXT NOT NULL,
                window_title TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_window_events_timestamp ON window_events(timestamp);
        """)
        # Activity mappings table
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS activity_mappings (
                activity TEXT PRIMARY KEY,
                meta_category TEXT NOT NULL DEFAULT 'other',
                first_seen TEXT NOT NULL DEFAULT (datetime('now')),
                frame_count INTEGER DEFAULT 0
            );
        """)
        self._seed_activity_mappings()
        # Memos table
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memos (
                date TEXT PRIMARY KEY,
                content TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        # Chat messages table
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                platform_message_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                channel_name TEXT DEFAULT '',
                guild_id TEXT DEFAULT '',
                guild_name TEXT DEFAULT '',
                author_id TEXT NOT NULL,
                author_name TEXT DEFAULT '',
                is_self BOOLEAN DEFAULT 0,
                content TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                metadata TEXT DEFAULT '',
                UNIQUE(platform, platform_message_id)
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp ON chat_messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_chat_messages_platform ON chat_messages(platform);
            CREATE INDEX IF NOT EXISTS idx_chat_messages_channel ON chat_messages(platform, channel_id);
        """)
        # Knowledge table
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_at TEXT NOT NULL,
                content TEXT NOT NULL,
                source_summary TEXT DEFAULT '',
                period_days INTEGER DEFAULT 0
            );
        """)
        # FTS tables — recreate if schema changed (e.g. new columns added)
        self._ensure_fts()
        self._rebuild_fts_if_needed()

    def _ensure_fts(self):
        """Create FTS tables, recreating if schema changed."""
        # Check if frames_fts exists and has the expected columns
        with contextlib.suppress(Exception):
            row = self._conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='frames_fts'"
            ).fetchone()
            if row and "foreground_window" not in (row["sql"] or ""):
                # Schema changed — drop and recreate
                self._conn.execute("DROP TABLE IF EXISTS frames_fts")
                self._conn.commit()
        self._conn.executescript(MIGRATE_FTS)

    def _rebuild_fts_if_needed(self):
        """Rebuild FTS indexes if they are empty but source tables have data."""
        frame_count = self._conn.execute("SELECT COUNT(*) FROM frames").fetchone()[0]
        fts_count = self._conn.execute("SELECT COUNT(*) FROM frames_fts").fetchone()[0]
        if frame_count > 0 and fts_count == 0:
            self._conn.execute("INSERT INTO frames_fts(frames_fts) VALUES('rebuild')")
            self._conn.execute("INSERT INTO summaries_fts(summaries_fts) VALUES('rebuild')")
            self._conn.commit()

    def _sync_frame_fts(self, frame_id: int, is_update: bool = False):
        """Sync a single frame to FTS index."""
        row = self._conn.execute(
            "SELECT claude_description, transcription, activity, foreground_window FROM frames WHERE id=?",
            (frame_id,),
        ).fetchone()
        if row:
            if is_update:
                # Delete old entry before re-inserting
                with contextlib.suppress(Exception):
                    self._conn.execute(
                        "INSERT INTO frames_fts(frames_fts, rowid, claude_description, transcription, activity, foreground_window) "
                        "VALUES('delete', ?, ?, ?, ?, ?)",
                        (
                            frame_id,
                            row["claude_description"] or "",
                            row["transcription"] or "",
                            row["activity"] or "",
                            row["foreground_window"] or "",
                        ),
                    )
            self._conn.execute(
                "INSERT INTO frames_fts(rowid, claude_description, transcription, activity, foreground_window) VALUES(?, ?, ?, ?, ?)",
                (
                    frame_id,
                    row["claude_description"] or "",
                    row["transcription"] or "",
                    row["activity"] or "",
                    row["foreground_window"] or "",
                ),
            )

    def _sync_summary_fts(self, summary_id: int):
        """Sync a single summary to FTS index."""
        row = self._conn.execute(
            "SELECT content FROM summaries WHERE id=?",
            (summary_id,),
        ).fetchone()
        if row:
            self._conn.execute(
                "INSERT INTO summaries_fts(rowid, content) VALUES(?, ?)",
                (summary_id, row["content"] or ""),
            )

    def _seed_activity_mappings(self):
        """Seed activity_mappings from existing frames if table is empty."""
        count = self._conn.execute("SELECT COUNT(*) FROM activity_mappings").fetchone()[0]
        if count > 0:
            return

        rows = self._conn.execute(
            "SELECT activity, COUNT(*) as cnt FROM frames WHERE activity != '' GROUP BY activity"
        ).fetchall()
        for r in rows:
            self._conn.execute(
                "INSERT OR IGNORE INTO activity_mappings (activity, meta_category, frame_count) VALUES (?, 'other', ?)",
                (r["activity"], r["cnt"]),
            )

        self._conn.commit()

    # --- Activity mappings ---

    def get_all_activity_mappings(self) -> list[dict]:
        """Get all activity → meta_category mappings, ordered by frame_count DESC."""
        rows = self._conn.execute(
            "SELECT activity, meta_category, frame_count FROM activity_mappings ORDER BY frame_count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_frequent_activities(self, limit: int = 15) -> list[str]:
        """Get top activities by frame_count."""
        rows = self._conn.execute(
            "SELECT activity FROM activity_mappings WHERE frame_count > 0 ORDER BY frame_count DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r["activity"] for r in rows]

    def upsert_activity_mapping(self, activity: str, meta_category: str):
        """Insert or update an activity mapping, incrementing frame_count."""
        self._conn.execute(
            "INSERT INTO activity_mappings (activity, meta_category, frame_count) "
            "VALUES (?, ?, 1) "
            "ON CONFLICT(activity) DO UPDATE SET "
            "frame_count = frame_count + 1, "
            "meta_category = CASE WHEN excluded.meta_category != 'other' THEN excluded.meta_category ELSE activity_mappings.meta_category END",
            (activity, meta_category),
        )
        self._conn.commit()

    def merge_activity(self, old: str, new: str):
        """Rename old activity to new across frames and activity_mappings."""
        self._conn.execute("UPDATE frames SET activity=? WHERE activity=?", (new, old))
        old_row = self._conn.execute(
            "SELECT meta_category, frame_count FROM activity_mappings WHERE activity=?", (old,)
        ).fetchone()
        if old_row:
            existing = self._conn.execute("SELECT 1 FROM activity_mappings WHERE activity=?", (new,)).fetchone()
            if existing:
                self._conn.execute(
                    "UPDATE activity_mappings SET frame_count = frame_count + ? WHERE activity=?",
                    (old_row["frame_count"], new),
                )
                self._conn.execute("DELETE FROM activity_mappings WHERE activity=?", (old,))
            else:
                self._conn.execute("UPDATE activity_mappings SET activity=? WHERE activity=?", (new, old))
        self._conn.commit()
        # Rebuild FTS so renamed activities are searchable under new name
        self._conn.execute("INSERT INTO frames_fts(frames_fts) VALUES('rebuild')")
        self._conn.commit()

    # --- Memos ---

    def get_memo(self, d: date) -> str:
        """Get memo content for a given date. Returns empty string if none."""
        row = self._conn.execute(
            "SELECT content FROM memos WHERE date=?",
            (d.isoformat(),),
        ).fetchone()
        return row["content"] if row else ""

    def upsert_memo(self, d: date, content: str):
        """Insert or update memo for a given date."""
        self._conn.execute(
            "INSERT INTO memos (date, content, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(date) DO UPDATE SET content=excluded.content, updated_at=datetime('now')",
            (d.isoformat(), content),
        )
        self._conn.commit()

    # --- Chat messages ---

    def insert_chat_message(self, msg: ChatMessage) -> int | None:
        """Insert a chat message. Returns ID, or None if duplicate."""
        try:
            cur = self._conn.execute(
                "INSERT INTO chat_messages "
                "(platform, platform_message_id, channel_id, channel_name, "
                "guild_id, guild_name, author_id, author_name, is_self, "
                "content, timestamp, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    msg.platform,
                    msg.platform_message_id,
                    msg.channel_id,
                    msg.channel_name,
                    msg.guild_id,
                    msg.guild_name,
                    msg.author_id,
                    msg.author_name,
                    msg.is_self,
                    msg.content,
                    msg.timestamp.isoformat(),
                    msg.metadata,
                ),
            )
            self._conn.commit()
            return cur.lastrowid
        except self._conn.IntegrityError:
            return None

    def get_chat_last_ids(self, platform: str) -> dict[str, str]:
        """Get last message ID per channel for a platform."""
        rows = self._conn.execute(
            "SELECT channel_id, platform_message_id FROM chat_messages "
            "WHERE platform=? AND id IN ("
            "  SELECT MAX(id) FROM chat_messages WHERE platform=? GROUP BY channel_id"
            ")",
            (platform, platform),
        ).fetchall()
        return {r["channel_id"]: r["platform_message_id"] for r in rows}

    def get_recent_chat_messages(self, since: datetime, limit: int = 50) -> list[ChatMessage]:
        """Get recent chat messages across all platforms since a given time."""
        rows = self._conn.execute(
            "SELECT * FROM chat_messages WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?",
            (since.isoformat(), limit),
        ).fetchall()
        return [self._row_to_chat_message(r) for r in reversed(rows)]

    def get_chat_messages_for_date(self, d: date, platform: str | None = None) -> list[ChatMessage]:
        """Get all chat messages for a given date."""
        start = datetime(d.year, d.month, d.day).isoformat()
        end = datetime(d.year, d.month, d.day, 23, 59, 59).isoformat()
        if platform:
            rows = self._conn.execute(
                "SELECT * FROM chat_messages WHERE timestamp BETWEEN ? AND ? AND platform=? ORDER BY timestamp",
                (start, end, platform),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM chat_messages WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
                (start, end),
            ).fetchall()
        return [self._row_to_chat_message(r) for r in rows]

    @staticmethod
    def _row_to_chat_message(row: sqlite3.Row) -> ChatMessage:
        return ChatMessage(
            id=row["id"],
            platform=row["platform"],
            platform_message_id=row["platform_message_id"],
            channel_id=row["channel_id"],
            channel_name=row["channel_name"] or "",
            guild_id=row["guild_id"] or "",
            guild_name=row["guild_name"] or "",
            author_id=row["author_id"],
            author_name=row["author_name"] or "",
            is_self=bool(row["is_self"]),
            content=row["content"] or "",
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metadata=row["metadata"] or "",
        )

    # --- Knowledge ---

    def get_latest_knowledge(self) -> str:
        """Get the latest knowledge profile content. Returns empty string if none."""
        row = self._conn.execute("SELECT content FROM knowledge ORDER BY id DESC LIMIT 1").fetchone()
        return row["content"] if row else ""

    def get_latest_knowledge_time(self) -> datetime | None:
        """Get the generation time of the latest knowledge profile."""
        row = self._conn.execute("SELECT generated_at FROM knowledge ORDER BY id DESC LIMIT 1").fetchone()
        return datetime.fromisoformat(row["generated_at"]) if row else None

    def insert_knowledge(self, content: str, source_summary: str = "", period_days: int = 0) -> int:
        """Insert a new knowledge profile. Returns the new row ID."""
        cur = self._conn.execute(
            "INSERT INTO knowledge (generated_at, content, source_summary, period_days) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), content, source_summary, period_days),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    # --- Knowledge data collection helpers ---

    def get_chat_channel_stats(self, limit: int = 20) -> list[dict]:
        """Get message counts per channel, ordered by activity."""
        rows = self._conn.execute(
            "SELECT platform, channel_name, guild_name, "
            "COUNT(*) as msg_count, "
            "COUNT(DISTINCT author_name) as author_count, "
            "MAX(timestamp) as last_active "
            "FROM chat_messages GROUP BY platform, channel_id "
            "ORDER BY msg_count DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_chat_samples_by_channel(self, channel_name: str, limit: int = 10) -> list[ChatMessage]:
        """Get recent messages from a specific channel."""
        rows = self._conn.execute(
            "SELECT * FROM chat_messages WHERE channel_name=? ORDER BY timestamp DESC LIMIT ?",
            (channel_name, limit),
        ).fetchall()
        return [self._row_to_chat_message(r) for r in reversed(rows)]

    def get_recent_summaries_by_scale(self, scale: str, limit: int = 7) -> list[Summary]:
        """Get the most recent summaries of a given scale."""
        rows = self._conn.execute(
            "SELECT * FROM summaries WHERE scale=? ORDER BY timestamp DESC LIMIT ?",
            (scale, limit),
        ).fetchall()
        return [self._row_to_summary(r) for r in reversed(rows)]

    def get_recent_memos(self, limit: int = 14) -> list[dict]:
        """Get recent memos, newest first."""
        rows = self._conn.execute(
            "SELECT date, content FROM memos WHERE content != '' ORDER BY date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_hourly_activity_distribution(self, days: int = 14) -> list[dict]:
        """Get activity distribution by hour over the last N days."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            "SELECT CAST(strftime('%%H', timestamp) AS INTEGER) as hour, "
            "activity, COUNT(*) as cnt "
            "FROM frames WHERE timestamp >= ? AND activity != '' "
            "GROUP BY hour, activity ORDER BY hour, cnt DESC",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self._conn.close()

    # --- Frames ---

    def insert_frame(self, frame: Frame) -> int:
        cur = self._conn.execute(
            """INSERT INTO frames (timestamp, path, screen_path, audio_path, transcription,
               brightness, motion_score, scene_type, claude_description, activity,
               screen_extra_paths, foreground_window, pose_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                frame.activity,
                frame.screen_extra_paths,
                frame.foreground_window,
                frame.pose_data,
            ),
        )
        self._conn.commit()
        frame_id = cur.lastrowid
        self._sync_frame_fts(frame_id)  # type: ignore[arg-type]
        self._conn.commit()
        return frame_id  # type: ignore[return-value]

    def update_frame_description(self, frame_id: int, description: str):
        self._conn.execute(
            "UPDATE frames SET claude_description=? WHERE id=?",
            (description, frame_id),
        )
        self._conn.commit()

    def update_frame_analysis(self, frame_id: int, description: str, activity: str):
        self._conn.execute(
            "UPDATE frames SET claude_description=?, activity=? WHERE id=?",
            (description, activity, frame_id),
        )
        self._sync_frame_fts(frame_id, is_update=True)
        self._conn.commit()

    def get_activity_stats(self, d: date) -> list[dict]:
        """Get activity statistics for a given date."""
        start = datetime(d.year, d.month, d.day).isoformat()
        end = datetime(d.year, d.month, d.day, 23, 59, 59).isoformat()
        rows = self._conn.execute(
            "SELECT activity, COUNT(*) as frame_count, "
            "CAST(strftime('%%H', timestamp) AS INTEGER) as hour "
            "FROM frames WHERE timestamp BETWEEN ? AND ? AND activity != '' "
            "GROUP BY activity, hour ORDER BY activity, hour",
            (start, end),
        ).fetchall()
        return [dict(r) for r in rows]

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
        row = self._conn.execute("SELECT * FROM frames ORDER BY timestamp DESC LIMIT 1").fetchone()
        return self._row_to_frame(row) if row else None

    def get_recent_frames(self, limit: int = 5) -> list[Frame]:
        rows = self._conn.execute(
            "SELECT * FROM frames ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_frame(r) for r in reversed(rows)]

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
        summary_id = cur.lastrowid
        self._sync_summary_fts(summary_id)  # type: ignore[arg-type]
        self._conn.commit()
        return summary_id  # type: ignore[return-value]

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

    # --- Reports ---

    def insert_report(self, report: Report) -> int:
        cur = self._conn.execute(
            """INSERT OR REPLACE INTO reports (date, content, generated_at, frame_count, focus_pct)
               VALUES (?, ?, ?, ?, ?)""",
            (
                report.date,
                report.content,
                report.generated_at.isoformat(),
                report.frame_count,
                report.focus_pct,
            ),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_report(self, d: date) -> Report | None:
        row = self._conn.execute(
            "SELECT * FROM reports WHERE date=?",
            (d.isoformat(),),
        ).fetchone()
        return self._row_to_report(row) if row else None

    def get_reports(self, limit: int = 30) -> list[Report]:
        rows = self._conn.execute(
            "SELECT * FROM reports ORDER BY date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_report(r) for r in rows]

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
            activity=row["activity"] or "",
            screen_extra_paths=row["screen_extra_paths"] or "",
            foreground_window=row["foreground_window"] or "",
            pose_data=row["pose_data"] if "pose_data" in row else "",  # noqa: SIM401 - sqlite3.Row has no .get()
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

    @staticmethod
    def _row_to_report(row: sqlite3.Row) -> Report:
        return Report(
            id=row["id"],
            date=row["date"],
            content=row["content"],
            generated_at=datetime.fromisoformat(row["generated_at"]),
            frame_count=row["frame_count"],
            focus_pct=row["focus_pct"],
        )
