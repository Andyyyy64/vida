use crate::db::AppDb;
use tauri::State;

#[tauri::command]
pub fn get_settings(_db: State<AppDb>) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({}))
}

#[tauri::command]
pub fn put_settings(
    _body: serde_json::Value,
    _db: State<AppDb>,
) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({"ok": true}))
}
