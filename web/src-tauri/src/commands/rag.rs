use std::time::Duration;

/// Hard cap on query length — prevents abusively large payloads reaching
/// the LLM and matches the daemon-side limit in rag_server.py.
const MAX_QUERY_LEN: usize = 2000;

/// Validate that a URL points to a loopback address only. The daemon's RAG
/// server binds to 127.0.0.1; allowing any other host would let an attacker
/// (who can set RAG_URL via settings or env) exfiltrate queries.
fn validate_rag_url(raw: &str) -> Result<reqwest::Url, String> {
    let url = reqwest::Url::parse(raw).map_err(|e| format!("invalid RAG_URL: {e}"))?;
    if url.scheme() != "http" && url.scheme() != "https" {
        return Err("RAG_URL must be http(s)".to_string());
    }
    match url.host_str() {
        Some("localhost") | Some("127.0.0.1") | Some("::1") | Some("[::1]") => Ok(url),
        Some(other) => Err(format!("RAG_URL host must be loopback, got {other}")),
        None => Err("RAG_URL missing host".to_string()),
    }
}

#[tauri::command]
pub async fn ask_rag(
    query: String,
    history: Vec<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    if query.trim().is_empty() {
        return Err("query is required".to_string());
    }
    if query.len() > MAX_QUERY_LEN {
        return Err("query too long".to_string());
    }
    if history.len() > 100 {
        return Err("history too long".to_string());
    }

    let raw = std::env::var("RAG_URL").unwrap_or_else(|_| "http://127.0.0.1:3003".to_string());
    let base = validate_rag_url(&raw)?;
    let endpoint = base.join("/ask").map_err(|e| e.to_string())?;

    // Short timeout so a hung RAG server can't block the UI indefinitely.
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(30))
        .connect_timeout(Duration::from_secs(5))
        .build()
        .map_err(|e| format!("http client init failed: {e}"))?;

    let body = serde_json::json!({
        "query": query,
        "history": history,
    });

    let res = client
        .post(endpoint)
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
