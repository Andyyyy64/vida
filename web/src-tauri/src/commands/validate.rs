//! Shared input-validation helpers for tauri command handlers.
//!
//! These functions exist so IPC commands reject malformed input at the
//! boundary instead of propagating garbage into SQL filters or filesystem
//! paths. None of the underlying queries are vulnerable to SQL injection
//! (rusqlite params are used everywhere), but unchecked dates can cause
//! pathological queries or silent data loss.

/// Validate a `YYYY-MM-DD` date string. Returns `Ok(())` when well-formed.
///
/// We intentionally do a cheap structural check plus a chrono parse so
/// values like `99999`, `'; DROP TABLE`, or multi-kilobyte strings are
/// rejected before reaching SQLite.
pub fn validate_date(date: &str) -> Result<(), String> {
    if date.len() != 10 {
        return Err("invalid date format (expected YYYY-MM-DD)".to_string());
    }
    chrono::NaiveDate::parse_from_str(date, "%Y-%m-%d")
        .map(|_| ())
        .map_err(|_| "invalid date".to_string())
}
