use crate::db::AppDb;
use crate::models::Summary;
use tauri::State;

#[tauri::command]
pub fn get_summaries(
    _date: String,
    _scale: Option<String>,
    _db: State<AppDb>,
) -> Result<Vec<Summary>, String> {
    Ok(vec![])
}
