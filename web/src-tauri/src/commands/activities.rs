use crate::db::AppDb;
use crate::models::ActivityInfo;
use std::collections::HashMap;
use tauri::State;

#[tauri::command]
pub fn list_activities(db: State<AppDb>) -> Result<Vec<ActivityInfo>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;

    let mut stmt = conn
        .prepare(
            "SELECT activity, COUNT(*) as frame_count
             FROM frames WHERE activity != ''
             GROUP BY activity ORDER BY frame_count DESC",
        )
        .map_err(|e| e.to_string())?;

    struct RawRow {
        activity: String,
        frame_count: i64,
    }

    let rows: Vec<RawRow> = stmt
        .query_map([], |row| {
            Ok(RawRow {
                activity: row.get(0)?,
                frame_count: row.get(1)?,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    // Drop conn lock before calling get_activity_mappings (which acquires its own lock)
    drop(stmt);
    drop(conn);

    let mappings = db.get_activity_mappings();

    let activities = rows
        .into_iter()
        .map(|r| ActivityInfo {
            activity: r.activity.clone(),
            meta_category: mappings
                .get(&r.activity)
                .cloned()
                .unwrap_or_else(|| "other".to_string()),
            frame_count: r.frame_count,
        })
        .collect();

    Ok(activities)
}

#[tauri::command]
pub fn get_activity_mappings(db: State<AppDb>) -> Result<HashMap<String, String>, String> {
    Ok(db.get_activity_mappings())
}
