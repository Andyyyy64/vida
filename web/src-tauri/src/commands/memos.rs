use crate::db::AppDb;
use crate::models::Memo;
use chrono::Local;
use tauri::State;

#[tauri::command]
pub fn get_memo(date: String, db: State<AppDb>) -> Result<Option<Memo>, String> {
    crate::commands::validate::validate_date(&date)?;
    let conn = db.conn.lock().map_err(|e| e.to_string())?;

    let mut stmt = conn
        .prepare("SELECT date, content, updated_at FROM memos WHERE date = ?1")
        .map_err(|e| e.to_string())?;

    let mut rows = stmt
        .query_map(rusqlite::params![date], |row| {
            Ok(Memo {
                date: row.get::<_, Option<String>>(0)?.unwrap_or_default(),
                content: row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                updated_at: row.get::<_, Option<String>>(2)?,
            })
        })
        .map_err(|e| e.to_string())?;

    match rows.next() {
        Some(row) => Ok(Some(row.map_err(|e| e.to_string())?)),
        None => Ok(Some(Memo {
            date,
            content: String::new(),
            updated_at: None,
        })),
    }
}

#[tauri::command]
pub fn put_memo(date: String, content: String, db: State<AppDb>) -> Result<Memo, String> {
    crate::commands::validate::validate_date(&date)?;
    if content.len() > 65536 {
        return Err("memo too large".to_string());
    }
    // Only allow editing today's memo (use local date, not UTC)
    let today = Local::now().format("%Y-%m-%d").to_string();
    if date != today {
        return Err("can only edit today's memo".to_string());
    }

    let conn = db.conn.lock().map_err(|e| e.to_string())?;

    conn.execute(
        "INSERT INTO memos (date, content, updated_at) VALUES (?1, ?2, datetime('now'))
         ON CONFLICT(date) DO UPDATE SET content=excluded.content, updated_at=datetime('now')",
        rusqlite::params![date, content],
    )
    .map_err(|e| e.to_string())?;

    // Read back the updated_at
    let updated_at: Option<String> = conn
        .query_row(
            "SELECT updated_at FROM memos WHERE date = ?1",
            rusqlite::params![date],
            |row| row.get(0),
        )
        .unwrap_or(None);

    Ok(Memo {
        date,
        content,
        updated_at,
    })
}
