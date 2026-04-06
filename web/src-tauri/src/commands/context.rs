use crate::db::AppDb;
use tauri::State;

#[tauri::command]
pub fn get_context(_db: State<AppDb>) -> Result<String, String> {
    Ok(String::new())
}

#[tauri::command]
pub fn put_context(_content: String, _db: State<AppDb>) -> Result<String, String> {
    Ok(String::new())
}
