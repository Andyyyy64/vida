use crate::db::AppDb;
use tauri::State;

#[tauri::command]
pub fn get_live_frame(_db: State<AppDb>) -> Result<Option<Vec<u8>>, String> {
    Ok(None)
}
