use crate::db::AppDb;
use crate::models::Frame;
use tauri::State;

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

#[tauri::command]
pub fn get_frames(date: String, db: State<AppDb>) -> Result<Vec<Frame>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let start = format!("{date}T00:00:00");
    let end = format!("{date}T23:59:59");

    let mut stmt = conn
        .prepare("SELECT * FROM frames WHERE timestamp BETWEEN ?1 AND ?2 ORDER BY timestamp")
        .map_err(|e| e.to_string())?;

    let rows = stmt
        .query_map(rusqlite::params![start, end], |row| row_to_frame(row))
        .map_err(|e| e.to_string())?;

    let mut frames = Vec::new();
    for row in rows {
        frames.push(row.map_err(|e| e.to_string())?);
    }
    Ok(frames)
}

#[tauri::command]
pub fn get_frame(id: i64, db: State<AppDb>) -> Result<Option<Frame>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare("SELECT * FROM frames WHERE id = ?1")
        .map_err(|e| e.to_string())?;

    let mut rows = stmt
        .query_map(rusqlite::params![id], |row| row_to_frame(row))
        .map_err(|e| e.to_string())?;

    match rows.next() {
        Some(row) => Ok(Some(row.map_err(|e| e.to_string())?)),
        None => Ok(None),
    }
}

#[tauri::command]
pub fn get_latest_frame(db: State<AppDb>) -> Result<Option<Frame>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare("SELECT * FROM frames ORDER BY timestamp DESC LIMIT 1")
        .map_err(|e| e.to_string())?;

    let mut rows = stmt
        .query_map([], |row| row_to_frame(row))
        .map_err(|e| e.to_string())?;

    match rows.next() {
        Some(row) => Ok(Some(row.map_err(|e| e.to_string())?)),
        None => Ok(None),
    }
}
