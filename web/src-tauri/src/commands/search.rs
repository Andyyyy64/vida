use crate::db::AppDb;
use crate::models::SearchResults;
use tauri::State;

#[tauri::command]
pub fn search_text(
    _q: String,
    _from: Option<String>,
    _to: Option<String>,
    _db: State<AppDb>,
) -> Result<SearchResults, String> {
    Ok(SearchResults::default())
}
