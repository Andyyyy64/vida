use crate::db::AppDb;
use tauri::State;

#[tauri::command]
pub fn get_live_frame(db: State<AppDb>) -> Result<Option<Vec<u8>>, String> {
    // Try to read live/latest.jpg first
    let live_path = db.data_dir.join("live").join("latest.jpg");
    if live_path.exists() {
        let data = std::fs::read(&live_path).map_err(|e| e.to_string())?;
        return Ok(Some(data));
    }

    // Fall back to the latest frame path from the DB
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let path: Option<String> = conn
        .query_row(
            "SELECT path FROM frames ORDER BY timestamp DESC LIMIT 1",
            [],
            |row| row.get(0),
        )
        .ok();

    if let Some(ref p) = path {
        let frame_path = db.data_dir.join(p);
        if frame_path.exists() {
            let data = std::fs::read(&frame_path).map_err(|e| e.to_string())?;
            return Ok(Some(data));
        }
    }

    Ok(None)
}
