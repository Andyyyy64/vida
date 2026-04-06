#[tauri::command]
pub fn get_devices() -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "cameras": [],
        "audio": []
    }))
}
