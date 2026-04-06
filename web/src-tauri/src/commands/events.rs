use crate::db::AppDb;
use crate::models::Event;
use tauri::State;

#[tauri::command]
pub fn get_events(_date: String, _db: State<AppDb>) -> Result<Vec<Event>, String> {
    Ok(vec![])
}
