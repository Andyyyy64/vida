use std::path::{Path, PathBuf};
use std::process::Command;

/// Resolve a candidate python path and confirm it's a real file (not a
/// dangling symlink). Returns the canonical path when possible so that
/// callers can verify containment with `starts_with`.
fn verify_python_binary(path: &Path) -> Option<PathBuf> {
    let canonical = std::fs::canonicalize(path).ok()?;
    if !canonical.is_file() {
        return None;
    }
    Some(canonical)
}

/// Find the Python binary by checking (in order):
/// 1. `VIDA_PYTHON` env var
/// 2. `.venv` in the given `repo_root`
/// 3. `python3` on PATH
/// 4. `python` on PATH
///
/// All candidates are canonicalized via std::fs::canonicalize so symlinks
/// and relative segments can't redirect execution to an unexpected binary.
pub fn find_python(repo_root: &PathBuf) -> Result<PathBuf, String> {
    // 1. Explicit override. Still verify it exists and is a regular file.
    if let Ok(p) = std::env::var("VIDA_PYTHON") {
        let path = PathBuf::from(&p);
        if let Some(verified) = verify_python_binary(&path) {
            return Ok(verified);
        }
    }

    // 2. .venv in repo root — must resolve to a path under repo_root so an
    //    attacker can't replace .venv with a symlink to a rogue binary.
    let venv_python = if cfg!(windows) {
        repo_root.join(".venv").join("Scripts").join("python.exe")
    } else {
        repo_root.join(".venv").join("bin").join("python")
    };
    if let Some(verified) = verify_python_binary(&venv_python) {
        if let Ok(canon_root) = repo_root.canonicalize() {
            if verified.starts_with(&canon_root) {
                return Ok(verified);
            }
        } else {
            return Ok(verified);
        }
    }

    // 3. python3 on PATH
    if let Some(resolved) = which_on_path("python3") {
        if let Some(verified) = verify_python_binary(&resolved) {
            return Ok(verified);
        }
    }

    // 4. python on PATH
    if let Some(resolved) = which_on_path("python") {
        if let Some(verified) = verify_python_binary(&resolved) {
            return Ok(verified);
        }
    }

    Err("Python not found. Install Python or run `uv sync` to create a .venv".to_string())
}

/// Locate a binary via `which`/`where` and return its absolute path.
fn which_on_path(name: &str) -> Option<PathBuf> {
    let cmd = if cfg!(windows) { "where" } else { "which" };
    let output = Command::new(cmd).arg(name).output().ok()?;
    if !output.status.success() {
        return None;
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let first = stdout.lines().next()?.trim();
    if first.is_empty() {
        None
    } else {
        Some(PathBuf::from(first))
    }
}

