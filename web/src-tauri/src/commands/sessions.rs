use crate::db::AppDb;
use crate::models::Session;
use tauri::State;

#[tauri::command]
pub fn get_sessions(date: String, db: State<AppDb>) -> Result<Vec<Session>, String> {
    crate::commands::validate::validate_date(&date)?;
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let start = format!("{date}T00:00:00");
    let end = format!("{date}T23:59:59");

    let mut stmt = conn
        .prepare(
            "SELECT id, timestamp, activity FROM frames
             WHERE timestamp BETWEEN ?1 AND ?2 AND activity != ''
             ORDER BY timestamp",
        )
        .map_err(|e| e.to_string())?;

    struct RawFrame {
        timestamp: String,
        activity: String,
    }

    let frames: Vec<RawFrame> = stmt
        .query_map(rusqlite::params![start, end], |row| {
            Ok(RawFrame {
                timestamp: row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                activity: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    if frames.is_empty() {
        return Ok(vec![]);
    }

    // Estimate frame interval from first two frames
    let interval_sec = if frames.len() >= 2 {
        let diff = parse_duration_secs(&frames[0].timestamp, &frames[1].timestamp);
        if diff > 0.0 && diff < 300.0 {
            diff.round() as i64
        } else {
            30
        }
    } else {
        30
    };

    // We need the meta-category mappings. Drop conn lock first since get_activity_mappings
    // acquires its own lock.
    drop(stmt);
    drop(conn);

    // Group consecutive frames with same activity into sessions
    let mut sessions = Vec::new();
    let mut session_start_idx = 0;
    let mut session_activity = frames[0].activity.clone();
    let mut frame_count: i64 = 1;

    for i in 1..frames.len() {
        if frames[i].activity == session_activity {
            frame_count += 1;
        } else {
            // Close current session
            let meta_category = db.get_meta_category(&session_activity);
            sessions.push(Session {
                activity: session_activity.clone(),
                meta_category,
                start_time: frames[session_start_idx].timestamp.clone(),
                end_time: frames[i - 1].timestamp.clone(),
                duration_sec: frame_count * interval_sec,
                frame_count,
            });
            // Start new session
            session_start_idx = i;
            session_activity = frames[i].activity.clone();
            frame_count = 1;
        }
    }

    // Close last session
    let meta_category = db.get_meta_category(&session_activity);
    sessions.push(Session {
        activity: session_activity,
        meta_category,
        start_time: frames[session_start_idx].timestamp.clone(),
        end_time: frames[frames.len() - 1].timestamp.clone(),
        duration_sec: frame_count * interval_sec,
        frame_count,
    });

    Ok(sessions)
}

/// Parse two ISO timestamp strings and return the difference in seconds.
fn parse_duration_secs(ts1: &str, ts2: &str) -> f64 {
    use chrono::NaiveDateTime;
    let fmt = "%Y-%m-%dT%H:%M:%S";
    let t1 = NaiveDateTime::parse_from_str(ts1, fmt)
        .or_else(|_| NaiveDateTime::parse_from_str(&ts1[..19.min(ts1.len())], fmt));
    let t2 = NaiveDateTime::parse_from_str(ts2, fmt)
        .or_else(|_| NaiveDateTime::parse_from_str(&ts2[..19.min(ts2.len())], fmt));
    match (t1, t2) {
        (Ok(a), Ok(b)) => (b - a).num_milliseconds() as f64 / 1000.0,
        _ => 0.0,
    }
}
