use crate::db::AppDb;
use tauri::State;

#[tauri::command]
pub fn get_status(db: State<AppDb>) -> Result<serde_json::Value, String> {
    let status_path = db.data_dir.join("status.json");
    match std::fs::read_to_string(&status_path) {
        Ok(content) => {
            let data: serde_json::Value =
                serde_json::from_str(&content).unwrap_or(serde_json::json!({
                    "running": false,
                    "camera": false,
                    "mic": false
                }));
            Ok(data)
        }
        Err(_) => Ok(serde_json::json!({
            "running": false,
            "camera": false,
            "mic": false
        })),
    }
}
