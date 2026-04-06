use crate::db::AppDb;
use tauri::State;

#[tauri::command]
pub fn get_status(_db: State<AppDb>) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "daemon": "unknown",
        "db": "ok"
    }))
}
