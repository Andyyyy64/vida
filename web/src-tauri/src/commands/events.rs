use crate::db::AppDb;
use crate::models::Event;
use tauri::State;

#[tauri::command]
pub fn get_events(date: String, db: State<AppDb>) -> Result<Vec<Event>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let start = format!("{date}T00:00:00");
    let end = format!("{date}T23:59:59");

    let mut stmt = conn
        .prepare("SELECT * FROM events WHERE timestamp BETWEEN ?1 AND ?2 ORDER BY timestamp")
        .map_err(|e| e.to_string())?;

    let rows = stmt
        .query_map(rusqlite::params![start, end], |row| {
            Ok(Event {
                id: row.get("id")?,
                timestamp: row.get::<_, Option<String>>("timestamp")?.unwrap_or_default(),
                event_type: row.get::<_, Option<String>>("event_type")?.unwrap_or_default(),
                description: row.get::<_, Option<String>>("description")?.unwrap_or_default(),
                frame_id: row.get::<_, Option<i64>>("frame_id")?,
            })
        })
        .map_err(|e| e.to_string())?;

    let mut events = Vec::new();
    for row in rows {
        events.push(row.map_err(|e| e.to_string())?);
    }
    Ok(events)
}
