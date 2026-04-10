use crate::db::AppDb;
use std::path::{Component, Path, PathBuf};
use tauri::State;

/// Return the resolved path only if it stays within `base`. Rejects paths
/// containing `..`, absolute paths, and anything whose canonical form
/// escapes the data directory (e.g. via symlinks).
fn safe_join(base: &Path, rel: &str) -> Option<PathBuf> {
    let rel_path = Path::new(rel);
    // Reject any absolute or parent-traversal components outright.
    for comp in rel_path.components() {
        match comp {
            Component::Normal(_) | Component::CurDir => {}
            _ => return None,
        }
    }
    let joined = base.join(rel_path);
    // Best-effort canonicalization: if the file exists, confirm it sits
    // under the canonical base. If canonicalize fails (e.g. file not yet
    // written), fall back to the component check above.
    if let (Ok(canon_base), Ok(canon_joined)) = (base.canonicalize(), joined.canonicalize()) {
        if !canon_joined.starts_with(&canon_base) {
            return None;
        }
    }
    Some(joined)
}

#[tauri::command]
pub fn get_live_frame(db: State<AppDb>) -> Result<Option<Vec<u8>>, String> {
    // Try to read live/latest.jpg first
    let live_path = db.data_dir.join("live").join("latest.jpg");
    if live_path.exists() {
        let data = std::fs::read(&live_path).map_err(|e| e.to_string())?;
        return Ok(Some(data));
    }

    // Fall back to the latest frame path from the DB
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let path: Option<String> = conn
        .query_row(
            "SELECT path FROM frames ORDER BY timestamp DESC LIMIT 1",
            [],
            |row| row.get(0),
        )
        .ok();

    if let Some(ref p) = path {
        let frame_path = match safe_join(&db.data_dir, p) {
            Some(fp) => fp,
            None => return Ok(None), // path escaped data_dir — refuse silently
        };
        if frame_path.exists() {
            let data = std::fs::read(&frame_path).map_err(|e| e.to_string())?;
            return Ok(Some(data));
        }
    }

    Ok(None)
}
