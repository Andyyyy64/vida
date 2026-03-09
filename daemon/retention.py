"""Data retention and cleanup for old frames, summaries, and events."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from daemon.storage.database import Database

log = logging.getLogger(__name__)


def cleanup_old_data(db: Database, data_dir: Path, retention_days: int) -> dict:
    """Delete frames, summaries, and events older than retention_days.

    Removes corresponding media files from disk (frames/, screens/, audio/).
    Reports are kept forever.

    Returns a dict with counts and freed bytes for logging/display.
    """
    cutoff = datetime.now() - timedelta(days=retention_days)
    cutoff_iso = cutoff.isoformat()

    log.info("Retention cleanup: deleting data older than %s (%d days)", cutoff.strftime("%Y-%m-%d"), retention_days)

    # --- Collect file paths from old frames before deleting ---
    rows = db._conn.execute(
        "SELECT path, screen_path, audio_path, screen_extra_paths FROM frames WHERE timestamp < ?",
        (cutoff_iso,),
    ).fetchall()

    file_paths: list[str] = []
    for row in rows:
        if row["path"]:
            file_paths.append(row["path"])
        if row["screen_path"]:
            file_paths.append(row["screen_path"])
        if row["audio_path"]:
            file_paths.append(row["audio_path"])
        if row["screen_extra_paths"]:
            for p in row["screen_extra_paths"].split(","):
                p = p.strip()
                if p:
                    file_paths.append(p)

    # --- Delete old frames from DB ---
    frame_count_row = db._conn.execute(
        "SELECT COUNT(*) as cnt FROM frames WHERE timestamp < ?",
        (cutoff_iso,),
    ).fetchone()
    frame_count = frame_count_row["cnt"]

    if frame_count > 0:
        db._conn.execute("DELETE FROM frames WHERE timestamp < ?", (cutoff_iso,))

    # --- Delete old summaries from DB ---
    summary_count_row = db._conn.execute(
        "SELECT COUNT(*) as cnt FROM summaries WHERE timestamp < ?",
        (cutoff_iso,),
    ).fetchone()
    summary_count = summary_count_row["cnt"]

    if summary_count > 0:
        db._conn.execute("DELETE FROM summaries WHERE timestamp < ?", (cutoff_iso,))

    # --- Delete old events from DB ---
    event_count_row = db._conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE timestamp < ?",
        (cutoff_iso,),
    ).fetchone()
    event_count = event_count_row["cnt"]

    if event_count > 0:
        db._conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff_iso,))

    # --- Delete old window_events from DB ---
    window_event_count = 0
    try:
        we_row = db._conn.execute(
            "SELECT COUNT(*) as cnt FROM window_events WHERE timestamp < ?",
            (cutoff_iso,),
        ).fetchone()
        window_event_count = we_row["cnt"]
        if window_event_count > 0:
            db._conn.execute("DELETE FROM window_events WHERE timestamp < ?", (cutoff_iso,))
    except Exception:
        pass  # table may not exist in older DBs

    db._conn.commit()

    # --- Rebuild FTS indexes after bulk delete ---
    if frame_count > 0:
        try:
            db._conn.execute("INSERT INTO frames_fts(frames_fts) VALUES('rebuild')")
            db._conn.commit()
        except Exception:
            pass
    if summary_count > 0:
        try:
            db._conn.execute("INSERT INTO summaries_fts(summaries_fts) VALUES('rebuild')")
            db._conn.commit()
        except Exception:
            pass

    # --- Remove media files from disk ---
    freed_bytes = 0
    files_deleted = 0
    for rel_path in file_paths:
        abs_path = data_dir / rel_path
        if abs_path.is_file():
            try:
                freed_bytes += abs_path.stat().st_size
                abs_path.unlink()
                files_deleted += 1
            except OSError as e:
                log.warning("Failed to delete %s: %s", abs_path, e)

    freed_mb = freed_bytes / (1024 * 1024)

    log.info(
        "Retention cleanup complete: %d frames, %d summaries, %d events, "
        "%d window_events deleted from DB; %d files removed (%.1f MB freed)",
        frame_count,
        summary_count,
        event_count,
        window_event_count,
        files_deleted,
        freed_mb,
    )

    return {
        "frames_deleted": frame_count,
        "summaries_deleted": summary_count,
        "events_deleted": event_count,
        "window_events_deleted": window_event_count,
        "files_deleted": files_deleted,
        "freed_bytes": freed_bytes,
    }
