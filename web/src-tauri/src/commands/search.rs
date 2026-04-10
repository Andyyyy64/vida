use crate::db::AppDb;
use crate::models::{Frame, SearchResults, Summary};
use tauri::State;

#[tauri::command]
pub fn search_text(
    q: String,
    from: Option<String>,
    to: Option<String>,
    db: State<AppDb>,
) -> Result<SearchResults, String> {
    // Reject empty or absurdly long queries — FTS5 can eat CPU on
    // complex MATCH expressions and we don't want the UI hanging.
    let q = q.trim().to_string();
    if q.is_empty() {
        return Ok(SearchResults { frames: vec![], summaries: vec![] });
    }
    if q.len() > 200 {
        return Err("query too long".to_string());
    }
    if let Some(ref f) = from {
        crate::commands::validate::validate_date(f)?;
    }
    if let Some(ref t) = to {
        crate::commands::validate::validate_date(t)?;
    }
    let conn = db.conn.lock().map_err(|e| e.to_string())?;

    let limit = 50i64;

    // Search frames via FTS5
    let frames = search_frames(&conn, &q, from.as_deref(), to.as_deref(), limit);

    // Search summaries via FTS5
    let summaries = search_summaries(&conn, &q, from.as_deref(), to.as_deref(), limit);

    Ok(SearchResults { frames, summaries })
}

fn search_frames(
    conn: &rusqlite::Connection,
    q: &str,
    from: Option<&str>,
    to: Option<&str>,
    limit: i64,
) -> Vec<Frame> {
    let has_range = from.is_some() && to.is_some();

    let sql = if has_range {
        "SELECT f.* FROM frames_fts fts
         JOIN frames f ON f.id = fts.rowid
         WHERE frames_fts MATCH ?1
           AND f.timestamp BETWEEN ?2 AND ?3
         ORDER BY rank LIMIT ?4"
    } else {
        "SELECT f.* FROM frames_fts fts
         JOIN frames f ON f.id = fts.rowid
         WHERE frames_fts MATCH ?1
         ORDER BY rank LIMIT ?2"
    };

    // Try exact query first, fall back to prefix search on error
    let result = if has_range {
        let start = format!("{}T00:00:00", from.unwrap());
        let end = format!("{}T23:59:59", to.unwrap());
        run_frame_query(conn, sql, q, Some(&start), Some(&end), limit)
    } else {
        run_frame_query(conn, sql, q, None, None, limit)
    };

    if let Ok(frames) = result {
        return frames;
    }

    // Fallback: prefix search
    let safe_q = format!("{}*", q.replace(['\'', '"'], ""));
    if has_range {
        let start = format!("{}T00:00:00", from.unwrap());
        let end = format!("{}T23:59:59", to.unwrap());
        run_frame_query(conn, sql, &safe_q, Some(&start), Some(&end), limit).unwrap_or_default()
    } else {
        run_frame_query(conn, sql, &safe_q, None, None, limit).unwrap_or_default()
    }
}

fn run_frame_query(
    conn: &rusqlite::Connection,
    sql: &str,
    q: &str,
    start: Option<&str>,
    end: Option<&str>,
    limit: i64,
) -> Result<Vec<Frame>, rusqlite::Error> {
    let mut stmt = conn.prepare(sql)?;

    let frames: Vec<Frame> = if let (Some(s), Some(e)) = (start, end) {
        let rows = stmt.query_map(rusqlite::params![q, s, e, limit], |row| row_to_frame(row))?;
        rows.filter_map(|r| r.ok()).collect()
    } else {
        let rows = stmt.query_map(rusqlite::params![q, limit], |row| row_to_frame(row))?;
        rows.filter_map(|r| r.ok()).collect()
    };

    Ok(frames)
}

fn row_to_frame(row: &rusqlite::Row) -> rusqlite::Result<Frame> {
    Ok(Frame {
        id: row.get("id")?,
        timestamp: row.get::<_, Option<String>>("timestamp")?.unwrap_or_default(),
        path: row.get::<_, Option<String>>("path")?.unwrap_or_default(),
        screen_path: row.get::<_, Option<String>>("screen_path")?.unwrap_or_default(),
        audio_path: row.get::<_, Option<String>>("audio_path")?.unwrap_or_default(),
        transcription: row.get::<_, Option<String>>("transcription")?.unwrap_or_default(),
        brightness: row.get::<_, Option<f64>>("brightness")?.unwrap_or_default(),
        motion_score: row.get::<_, Option<f64>>("motion_score")?.unwrap_or_default(),
        scene_type: row.get::<_, Option<String>>("scene_type")?.unwrap_or_default(),
        claude_description: row.get::<_, Option<String>>("claude_description")?.unwrap_or_default(),
        activity: row.get::<_, Option<String>>("activity")?.unwrap_or_default(),
        screen_extra_paths: row.get::<_, Option<String>>("screen_extra_paths")?.unwrap_or_default(),
        foreground_window: row.get::<_, Option<String>>("foreground_window")?.unwrap_or_default(),
    })
}

fn search_summaries(
    conn: &rusqlite::Connection,
    q: &str,
    from: Option<&str>,
    to: Option<&str>,
    limit: i64,
) -> Vec<Summary> {
    let has_range = from.is_some() && to.is_some();

    let sql = if has_range {
        "SELECT s.* FROM summaries_fts sfts
         JOIN summaries s ON s.id = sfts.rowid
         WHERE summaries_fts MATCH ?1
           AND s.timestamp BETWEEN ?2 AND ?3
         ORDER BY rank LIMIT ?4"
    } else {
        "SELECT s.* FROM summaries_fts sfts
         JOIN summaries s ON s.id = sfts.rowid
         WHERE summaries_fts MATCH ?1
         ORDER BY rank LIMIT ?2"
    };

    let result = if has_range {
        let start = format!("{}T00:00:00", from.unwrap());
        let end = format!("{}T23:59:59", to.unwrap());
        run_summary_query(conn, sql, q, Some(&start), Some(&end), limit)
    } else {
        run_summary_query(conn, sql, q, None, None, limit)
    };

    if let Ok(summaries) = result {
        return summaries;
    }

    // Fallback: prefix search
    let safe_q = format!("{}*", q.replace(['\'', '"'], ""));
    if has_range {
        let start = format!("{}T00:00:00", from.unwrap());
        let end = format!("{}T23:59:59", to.unwrap());
        run_summary_query(conn, sql, &safe_q, Some(&start), Some(&end), limit).unwrap_or_default()
    } else {
        run_summary_query(conn, sql, &safe_q, None, None, limit).unwrap_or_default()
    }
}

fn run_summary_query(
    conn: &rusqlite::Connection,
    sql: &str,
    q: &str,
    start: Option<&str>,
    end: Option<&str>,
    limit: i64,
) -> Result<Vec<Summary>, rusqlite::Error> {
    let mut stmt = conn.prepare(sql)?;

    let summaries: Vec<Summary> = if let (Some(s), Some(e)) = (start, end) {
        let rows = stmt.query_map(rusqlite::params![q, s, e, limit], |row| row_to_summary(row))?;
        rows.filter_map(|r| r.ok()).collect()
    } else {
        let rows = stmt.query_map(rusqlite::params![q, limit], |row| row_to_summary(row))?;
        rows.filter_map(|r| r.ok()).collect()
    };

    Ok(summaries)
}

fn row_to_summary(row: &rusqlite::Row) -> rusqlite::Result<Summary> {
    Ok(Summary {
        id: row.get("id")?,
        timestamp: row.get::<_, Option<String>>("timestamp")?.unwrap_or_default(),
        scale: row.get::<_, Option<String>>("scale")?.unwrap_or_default(),
        content: row.get::<_, Option<String>>("content")?.unwrap_or_default(),
        frame_count: row.get::<_, Option<i64>>("frame_count")?.unwrap_or_default(),
    })
}
