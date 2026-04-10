use crate::db::AppDb;
use tauri::State;

/// Hard cap on context.md size (matches roughly 30k tokens of UTF-8 text).
const MAX_CONTEXT_BYTES: usize = 128 * 1024;

/// Resolve the context.md path and confirm it sits under data_dir. This
/// guards against future refactors that might accept a user-controlled
/// filename — traversal is impossible today but worth enforcing as a
/// defence in depth.
fn context_path(db: &AppDb) -> Result<std::path::PathBuf, String> {
    let ctx_path = db.data_dir.join("context.md");
    // Verify via canonicalize when possible (file may not exist yet).
    if let (Ok(canon_base), Ok(canon_ctx)) = (db.data_dir.canonicalize(), ctx_path.canonicalize()) {
        if !canon_ctx.starts_with(&canon_base) {
            return Err("context path outside data_dir".to_string());
        }
    }
    Ok(ctx_path)
}

#[tauri::command]
pub fn get_context(db: State<AppDb>) -> Result<String, String> {
    let ctx_path = context_path(&db)?;
    match std::fs::read_to_string(&ctx_path) {
        Ok(content) => Ok(content),
        Err(_) => Ok(String::new()),
    }
}

#[tauri::command]
pub fn put_context(content: String, db: State<AppDb>) -> Result<String, String> {
    if content.len() > MAX_CONTEXT_BYTES {
        return Err("context too large".to_string());
    }
    std::fs::create_dir_all(&db.data_dir).map_err(|e| e.to_string())?;
    let ctx_path = context_path(&db)?;
    std::fs::write(&ctx_path, &content).map_err(|e| format!("Failed to save context: {e}"))?;
    Ok(content)
}
