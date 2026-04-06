use crate::db::AppDb;
use tauri::State;

#[tauri::command]
pub fn export_frames_csv(
    _date: String,
    _format: Option<String>,
    _db: State<AppDb>,
) -> Result<String, String> {
    Ok(String::new())
}

#[tauri::command]
pub fn export_summaries_csv(
    _from: String,
    _to: String,
    _format: Option<String>,
    _db: State<AppDb>,
) -> Result<String, String> {
    Ok(String::new())
}

#[tauri::command]
pub fn export_report(_date: String, _db: State<AppDb>) -> Result<String, String> {
    Ok(String::new())
}
