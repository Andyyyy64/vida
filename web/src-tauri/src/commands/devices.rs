use std::path::PathBuf;
use std::process::Command;

use crate::python;

fn get_repo_root() -> PathBuf {
    if let Ok(p) = std::env::var("HOMELIFE_DAEMON_SRC") {
        return PathBuf::from(p);
    }
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .parent()
        .and_then(|p| p.parent())
        .unwrap_or(&manifest_dir)
        .to_path_buf()
}

#[tauri::command]
pub async fn get_devices() -> Result<serde_json::Value, String> {
    let repo_root = get_repo_root();
    let python = match python::find_python(&repo_root) {
        Ok(p) => p,
        Err(e) => {
            return Ok(serde_json::json!({
                "cameras": [],
                "audio": [],
                "error": e
            }));
        }
    };

    let daemon_src = &repo_root;
    let script = daemon_src.join("daemon").join("devices.py");

    let output = Command::new(&python)
        .arg(&script)
        .current_dir(&daemon_src)
        .env("PYTHONPATH", &daemon_src)
        .output()
        .map_err(|e| format!("Failed to run device enumeration: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Ok(serde_json::json!({
            "cameras": [],
            "audio": [],
            "error": format!("{}", &stderr[..stderr.len().min(300)])
        }));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let data: serde_json::Value =
        serde_json::from_str(&stdout).map_err(|_| "Failed to parse device list".to_string())?;

    Ok(data)
}
