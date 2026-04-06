use crate::db::AppDb;
use crate::models::DataStats;
use tauri::State;

#[tauri::command]
pub fn get_data_stats(_db: State<AppDb>) -> Result<DataStats, String> {
    Ok(DataStats::default())
}

#[tauri::command]
pub fn export_table(
    _table: String,
    _format: Option<String>,
    _db: State<AppDb>,
) -> Result<String, String> {
    Ok(String::new())
}
