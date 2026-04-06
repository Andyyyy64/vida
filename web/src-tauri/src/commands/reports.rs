use crate::db::AppDb;
use crate::models::Report;
use tauri::State;

#[tauri::command]
pub fn get_report(_date: String, _db: State<AppDb>) -> Result<Option<Report>, String> {
    Ok(None)
}

#[tauri::command]
pub fn list_reports(_db: State<AppDb>) -> Result<Vec<Report>, String> {
    Ok(vec![])
}
