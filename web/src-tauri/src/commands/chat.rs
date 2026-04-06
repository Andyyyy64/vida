use crate::db::AppDb;
use crate::models::ChatData;
use tauri::State;

#[tauri::command]
pub fn get_chat(_date: String, _db: State<AppDb>) -> Result<ChatData, String> {
    Ok(ChatData::default())
}
