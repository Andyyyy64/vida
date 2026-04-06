use crate::db::AppDb;
use crate::models::ActivityInfo;
use std::collections::HashMap;
use tauri::State;

#[tauri::command]
pub fn list_activities(_db: State<AppDb>) -> Result<Vec<ActivityInfo>, String> {
    Ok(vec![])
}

#[tauri::command]
pub fn get_activity_mappings(_db: State<AppDb>) -> Result<HashMap<String, String>, String> {
    Ok(_db.get_activity_mappings())
}
