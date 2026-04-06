use crate::db::AppDb;
use crate::models::{ActivityStats, AppStat, DayStats, RangeStats};
use tauri::State;

#[tauri::command]
pub fn get_stats(_date: String, _db: State<AppDb>) -> Result<DayStats, String> {
    Ok(DayStats::default())
}

#[tauri::command]
pub fn get_activities(_date: String, _db: State<AppDb>) -> Result<ActivityStats, String> {
    Ok(ActivityStats::default())
}

#[tauri::command]
pub fn get_apps(_date: String, _db: State<AppDb>) -> Result<Vec<AppStat>, String> {
    Ok(vec![])
}

#[tauri::command]
pub fn get_dates(_db: State<AppDb>) -> Result<Vec<String>, String> {
    Ok(vec![])
}

#[tauri::command]
pub fn get_range_stats(
    _from: String,
    _to: String,
    _db: State<AppDb>,
) -> Result<RangeStats, String> {
    Ok(RangeStats::default())
}
