use std::path::PathBuf;
use std::process::Command;

/// Find the Python binary by checking (in order):
/// 1. `HOMELIFE_PYTHON` env var
/// 2. `.venv` in the given `repo_root`
/// 3. `python3` on PATH
/// 4. `python` on PATH
pub fn find_python(repo_root: &PathBuf) -> Result<PathBuf, String> {
    // 1. Explicit override
    if let Ok(p) = std::env::var("HOMELIFE_PYTHON") {
        let path = PathBuf::from(&p);
        if path.exists() {
            return Ok(path);
        }
    }

    // 2. .venv in repo root
    let venv_python = if cfg!(windows) {
        repo_root.join(".venv").join("Scripts").join("python.exe")
    } else {
        repo_root.join(".venv").join("bin").join("python")
    };
    if venv_python.exists() {
        return Ok(venv_python);
    }

    // 3. python3 on PATH
    if is_on_path("python3") {
        return Ok(PathBuf::from("python3"));
    }

    // 4. python on PATH
    if is_on_path("python") {
        return Ok(PathBuf::from("python"));
    }

    Err("Python not found. Install Python or run `uv sync` to create a .venv".to_string())
}

fn is_on_path(name: &str) -> bool {
    let cmd = if cfg!(windows) { "where" } else { "which" };
    Command::new(cmd)
        .arg(name)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}
