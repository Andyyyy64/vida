
#[tauri::command]
pub async fn ask_rag(
    query: String,
    history: Vec<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    let rag_url = std::env::var("RAG_URL").unwrap_or_else(|_| "http://localhost:3003".to_string());

    let client = reqwest::Client::new();
    let body = serde_json::json!({
        "query": query,
        "history": history,
    });

    let res = client
        .post(format!("{rag_url}/ask"))
        .json(&body)
        .send()
        .await
        .map_err(|_| "RAG server unavailable".to_string())?;

    let data: serde_json::Value = res
        .json()
        .await
        .map_err(|e| format!("Failed to parse RAG response: {e}"))?;

    Ok(data)
}
