use crate::db::AppDb;
use crate::python;
use std::process::Command;
use tauri::State;

#[tauri::command]
pub async fn get_devices(db: State<'_, AppDb>) -> Result<serde_json::Value, String> {
    let repo_root = &db.config_dir;
    let python = match python::find_python(repo_root) {
        Ok(p) => p,
        Err(e) => {
            return Ok(serde_json::json!({
                "cameras": [],
                "audio": [],
                "error": e
            }));
        }
    };

    let daemon_src = &db.daemon_src;
    let script = daemon_src.join("daemon").join("devices.py");

    // Canonicalize both the script and the daemon root so symlinks can't
    // redirect execution to an attacker-controlled file. Refuse to run
    // anything outside the bundled daemon directory.
    let canon_script = match std::fs::canonicalize(&script) {
        Ok(p) => p,
        Err(_) => {
            return Ok(serde_json::json!({
                "cameras": [], "audio": [],
                "error": "devices.py not found"
            }));
        }
    };
    let canon_daemon = match std::fs::canonicalize(daemon_src) {
        Ok(p) => p,
        Err(_) => {
            return Ok(serde_json::json!({
                "cameras": [], "audio": [],
                "error": "daemon dir not found"
            }));
        }
    };
    if !canon_script.starts_with(&canon_daemon) || !canon_script.is_file() {
        return Ok(serde_json::json!({
            "cameras": [], "audio": [],
            "error": "devices.py outside daemon dir"
        }));
    }

    let mut cmd = Command::new(&python);
    cmd.arg(&canon_script)
        .current_dir(&canon_daemon)
        .env("PYTHONPATH", &canon_daemon);

    crate::hide_window(&mut cmd);

    let output = cmd
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
