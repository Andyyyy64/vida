use crate::db::AppDb;
use crate::models::Session;
use tauri::State;

#[tauri::command]
pub fn get_sessions(_date: String, _db: State<AppDb>) -> Result<Vec<Session>, String> {
    Ok(vec![])
}
