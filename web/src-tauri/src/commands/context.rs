use crate::db::AppDb;
use tauri::State;

#[tauri::command]
pub fn get_context(db: State<AppDb>) -> Result<String, String> {
    let ctx_path = db.data_dir.join("context.md");
    match std::fs::read_to_string(&ctx_path) {
        Ok(content) => Ok(content),
        Err(_) => Ok(String::new()),
    }
}

#[tauri::command]
pub fn put_context(content: String, db: State<AppDb>) -> Result<String, String> {
    std::fs::create_dir_all(&db.data_dir).map_err(|e| e.to_string())?;
    let ctx_path = db.data_dir.join("context.md");
    std::fs::write(&ctx_path, &content).map_err(|e| format!("Failed to save context: {e}"))?;
    Ok(content)
}
