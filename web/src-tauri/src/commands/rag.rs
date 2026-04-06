#[tauri::command]
pub fn ask_rag(
    _query: String,
    _history: Vec<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "answer": "",
        "sources": []
    }))
}
