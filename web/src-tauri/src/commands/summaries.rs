use crate::db::AppDb;
use crate::models::Summary;
use tauri::State;

fn row_to_summary(row: &rusqlite::Row) -> rusqlite::Result<Summary> {
    Ok(Summary {
        id: row.get("id")?,
        timestamp: row.get::<_, Option<String>>("timestamp")?.unwrap_or_default(),
        scale: row.get::<_, Option<String>>("scale")?.unwrap_or_default(),
        content: row.get::<_, Option<String>>("content")?.unwrap_or_default(),
        frame_count: row.get::<_, Option<i64>>("frame_count")?.unwrap_or_default(),
    })
}

#[tauri::command]
pub fn get_summaries(
    date: String,
    scale: Option<String>,
    db: State<AppDb>,
) -> Result<Vec<Summary>, String> {
    crate::commands::validate::validate_date(&date)?;
    // Scale must be one of the known summary intervals.
    if let Some(ref s) = scale {
        if !matches!(s.as_str(), "10m" | "30m" | "1h" | "6h" | "12h" | "24h") {
            return Err("invalid scale".to_string());
        }
    }
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let start = format!("{date}T00:00:00");
    let end = format!("{date}T23:59:59");

    if let Some(ref s) = scale {
        let mut stmt = conn
            .prepare(
                "SELECT * FROM summaries WHERE timestamp BETWEEN ?1 AND ?2 AND scale = ?3 ORDER BY timestamp",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(rusqlite::params![start, end, s], |row| row_to_summary(row))
            .map_err(|e| e.to_string())?;
        let summaries: Vec<Summary> = rows.filter_map(|r| r.ok()).collect();
        Ok(summaries)
    } else {
        let mut stmt = conn
            .prepare(
                "SELECT * FROM summaries WHERE timestamp BETWEEN ?1 AND ?2 ORDER BY timestamp",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(rusqlite::params![start, end], |row| row_to_summary(row))
            .map_err(|e| e.to_string())?;
        let summaries: Vec<Summary> = rows.filter_map(|r| r.ok()).collect();
        Ok(summaries)
    }
}
