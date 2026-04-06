use crate::db::AppDb;
use crate::models::DataStats;
use std::collections::HashMap;
use tauri::State;

const EXPORT_TABLES: &[&str] = &[
    "frames",
    "summaries",
    "events",
    "chat_messages",
    "memos",
    "reports",
    "activity_mappings",
];

const ALL_TABLES: &[&str] = &[
    "frames",
    "summaries",
    "events",
    "chat_messages",
    "memos",
    "reports",
    "activity_mappings",
    "window_events",
    "knowledge",
];

fn to_csv(conn: &rusqlite::Connection, table: &str) -> Result<String, String> {
    let sql = format!("SELECT * FROM {table} ORDER BY rowid");
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let col_count = stmt.column_count();
    let col_names: Vec<String> = (0..col_count)
        .map(|i| stmt.column_name(i).unwrap_or("").to_string())
        .collect();

    let mut rows_data = Vec::new();
    let mut rows = stmt.query([]).map_err(|e| e.to_string())?;
    while let Some(row) = rows.next().map_err(|e| e.to_string())? {
        let mut vals = Vec::new();
        for i in 0..col_count {
            let val: String = row
                .get::<_, Option<String>>(i)
                .unwrap_or(None)
                .unwrap_or_default();
            vals.push(csv_escape(&val));
        }
        rows_data.push(vals.join(","));
    }

    let mut output = Vec::new();
    output.push(col_names.join(","));
    output.extend(rows_data);
    Ok(output.join("\n"))
}

fn to_json(conn: &rusqlite::Connection, table: &str) -> Result<String, String> {
    let sql = format!("SELECT * FROM {table} ORDER BY rowid");
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let col_count = stmt.column_count();
    let col_names: Vec<String> = (0..col_count)
        .map(|i| stmt.column_name(i).unwrap_or("").to_string())
        .collect();

    let mut arr = Vec::new();
    let mut rows = stmt.query([]).map_err(|e| e.to_string())?;
    while let Some(row) = rows.next().map_err(|e| e.to_string())? {
        let mut obj = serde_json::Map::new();
        for (i, name) in col_names.iter().enumerate() {
            let val: rusqlite::types::Value = row.get_unwrap(i);
            let json_val = match val {
                rusqlite::types::Value::Null => serde_json::Value::Null,
                rusqlite::types::Value::Integer(n) => serde_json::Value::Number(n.into()),
                rusqlite::types::Value::Real(f) => {
                    serde_json::Number::from_f64(f)
                        .map(serde_json::Value::Number)
                        .unwrap_or(serde_json::Value::Null)
                }
                rusqlite::types::Value::Text(s) => serde_json::Value::String(s),
                rusqlite::types::Value::Blob(b) => {
                    serde_json::Value::String(format!("<blob:{} bytes>", b.len()))
                }
            };
            obj.insert(name.clone(), json_val);
        }
        arr.push(serde_json::Value::Object(obj));
    }

    serde_json::to_string_pretty(&arr).map_err(|e| e.to_string())
}

fn csv_escape(s: &str) -> String {
    if s.contains(',') || s.contains('"') || s.contains('\n') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}

#[tauri::command]
pub fn get_data_stats(db: State<AppDb>) -> Result<DataStats, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;

    let mut counts: HashMap<String, i64> = HashMap::new();
    for table in ALL_TABLES {
        let count: i64 = conn
            .query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |row| {
                row.get(0)
            })
            .unwrap_or(0);
        counts.insert(table.to_string(), count);
    }

    let first_date: String = conn
        .query_row("SELECT MIN(timestamp) FROM frames", [], |row| {
            row.get::<_, Option<String>>(0)
        })
        .unwrap_or(None)
        .unwrap_or_default();

    let last_date: String = conn
        .query_row("SELECT MAX(timestamp) FROM frames", [], |row| {
            row.get::<_, Option<String>>(0)
        })
        .unwrap_or(None)
        .unwrap_or_default();

    let db_path = db.data_dir.join("life.db");
    let db_size_bytes = std::fs::metadata(&db_path)
        .map(|m| m.len())
        .unwrap_or(0);

    Ok(DataStats {
        counts,
        first_date,
        last_date,
        db_size_bytes,
    })
}

#[tauri::command]
pub fn export_table(
    table: String,
    format: Option<String>,
    db: State<AppDb>,
) -> Result<String, String> {
    if !EXPORT_TABLES.contains(&table.as_str()) {
        return Err("invalid table".to_string());
    }

    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let fmt = format.unwrap_or_else(|| "csv".to_string());

    if fmt == "json" {
        to_json(&conn, &table)
    } else {
        to_csv(&conn, &table)
    }
}
