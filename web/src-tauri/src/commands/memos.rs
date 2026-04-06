use crate::db::AppDb;
use crate::models::Memo;
use tauri::State;

#[tauri::command]
pub fn get_memo(_date: String, _db: State<AppDb>) -> Result<Option<Memo>, String> {
    Ok(None)
}

#[tauri::command]
pub fn put_memo(_date: String, _content: String, _db: State<AppDb>) -> Result<Memo, String> {
    Ok(Memo {
        date: _date,
        content: _content,
        updated_at: None,
    })
}
