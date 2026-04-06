use crate::db::AppDb;
use crate::models::Report;
use tauri::State;

fn row_to_report(row: &rusqlite::Row) -> rusqlite::Result<Report> {
    Ok(Report {
        id: row.get("id")?,
        date: row.get::<_, Option<String>>("date")?.unwrap_or_default(),
        content: row.get::<_, Option<String>>("content")?.unwrap_or_default(),
        generated_at: row.get::<_, Option<String>>("generated_at")?.unwrap_or_default(),
        frame_count: row.get::<_, Option<i64>>("frame_count")?.unwrap_or_default(),
        focus_pct: row.get::<_, Option<f64>>("focus_pct")?.unwrap_or_default(),
    })
}

#[tauri::command]
pub fn get_report(date: String, db: State<AppDb>) -> Result<Option<Report>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;

    // The reports table may not exist yet
    let mut stmt = match conn.prepare("SELECT * FROM reports WHERE date = ?1") {
        Ok(s) => s,
        Err(_) => return Ok(None),
    };

    let mut rows = stmt
        .query_map(rusqlite::params![date], |row| row_to_report(row))
        .map_err(|e| e.to_string())?;

    match rows.next() {
        Some(row) => Ok(Some(row.map_err(|e| e.to_string())?)),
        None => Ok(None),
    }
}

#[tauri::command]
pub fn list_reports(db: State<AppDb>) -> Result<Vec<Report>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;

    let mut stmt = match conn.prepare("SELECT * FROM reports ORDER BY date DESC LIMIT 30") {
        Ok(s) => s,
        Err(_) => return Ok(vec![]),
    };

    let rows = stmt
        .query_map([], |row| row_to_report(row))
        .map_err(|e| e.to_string())?;

    let mut reports = Vec::new();
    for row in rows {
        reports.push(row.map_err(|e| e.to_string())?);
    }
    Ok(reports)
}
