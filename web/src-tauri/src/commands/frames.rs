use crate::db::AppDb;
use crate::models::Frame;
use tauri::State;

#[tauri::command]
pub fn get_frames(_date: String, _db: State<AppDb>) -> Result<Vec<Frame>, String> {
    Ok(vec![])
}

#[tauri::command]
pub fn get_frame(_id: i64, _db: State<AppDb>) -> Result<Option<Frame>, String> {
    Ok(None)
}

#[tauri::command]
pub fn get_latest_frame(_db: State<AppDb>) -> Result<Option<Frame>, String> {
    Ok(None)
}
