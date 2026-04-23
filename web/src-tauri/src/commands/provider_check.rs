use crate::db::AppDb;
use crate::python;
use serde::Deserialize;
use std::io::Write;
use std::process::{Command, Stdio};
use tauri::State;

#[derive(Deserialize)]
pub struct ProviderCheckRequest {
    provider: String,
    gemini_model: Option<String>,
    claude_model: Option<String>,
    codex_model: Option<String>,
    gemini_api_key: Option<String>,
}

#[tauri::command]
pub async fn validate_provider(
    body: ProviderCheckRequest,
    db: State<'_, AppDb>,
) -> Result<serde_json::Value, String> {
    let provider = body.provider.trim();
    if !matches!(provider, "gemini" | "claude" | "codex" | "external") {
        return Ok(serde_json::json!({
            "ok": false,
            "code": "invalid_provider",
        }));
    }

    if provider == "external" {
        return Ok(serde_json::json!({
            "ok": true,
            "code": "external",
        }));
    }

    let repo_root = &db.config_dir;
    let python = match python::find_python(repo_root) {
        Ok(p) => p,
        Err(_) => {
            return Ok(serde_json::json!({
                "ok": false,
                "code": "python_not_found",
            }));
        }
    };

    let daemon_src = &db.daemon_src;
    let canon_daemon = match std::fs::canonicalize(daemon_src) {
        Ok(p) => p,
        Err(_) => {
            return Ok(serde_json::json!({
                "ok": false,
                "code": "daemon_not_found",
            }));
        }
    };
    let provider_check = canon_daemon.join("daemon").join("provider_check.py");
    if !provider_check.is_file() {
        return Ok(serde_json::json!({
            "ok": false,
            "code": "checker_not_found",
        }));
    }

    let gemini_api_key = body
        .gemini_api_key
        .filter(|v| !v.trim().is_empty())
        .or_else(|| db.get_setting("env.GEMINI_API_KEY"));

    let payload = serde_json::json!({
        "provider": provider,
        "gemini_model": body.gemini_model.unwrap_or_else(|| "gemini-3.1-flash-lite-preview".to_string()),
        "claude_model": body.claude_model.unwrap_or_else(|| "haiku".to_string()),
        "codex_model": body.codex_model.unwrap_or_else(|| "gpt-5.4".to_string()),
        "gemini_api_key": gemini_api_key.unwrap_or_default(),
    });

    let mut cmd = Command::new(&python);
    cmd.arg("-m")
        .arg("daemon.provider_check")
        .current_dir(&canon_daemon)
        .env("PYTHONPATH", &canon_daemon)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    crate::hide_window(&mut cmd);

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to launch provider checker: {e}"))?;

    if let Some(stdin) = child.stdin.as_mut() {
        stdin
            .write_all(payload.to_string().as_bytes())
            .map_err(|e| format!("Failed to send validation payload: {e}"))?;
    }
    let _ = child.stdin.take();

    let output = child
        .wait_with_output()
        .map_err(|e| format!("Failed to wait for provider checker: {e}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    if !output.status.success() && stdout.trim().is_empty() {
        return Ok(serde_json::json!({
            "ok": false,
            "code": "request_failed",
            "detail": stderr.trim().chars().take(300).collect::<String>(),
        }));
    }

    serde_json::from_str(&stdout)
        .map_err(|_| format!("Failed to parse provider validation result: {}", stderr.trim()))
}
