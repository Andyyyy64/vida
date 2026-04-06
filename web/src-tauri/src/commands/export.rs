use crate::db::AppDb;
use tauri::State;

fn csv_escape(s: &str) -> String {
    if s.contains(',') || s.contains('"') || s.contains('\n') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}

fn query_to_csv(conn: &rusqlite::Connection, sql: &str, params: &[&dyn rusqlite::types::ToSql]) -> Result<String, String> {
    let mut stmt = conn.prepare(sql).map_err(|e| e.to_string())?;
    let col_count = stmt.column_count();
    let col_names: Vec<String> = (0..col_count)
        .map(|i| stmt.column_name(i).unwrap_or("").to_string())
        .collect();

    let mut rows_data = Vec::new();
    let mut rows = stmt.query(params).map_err(|e| e.to_string())?;
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

fn query_to_json(conn: &rusqlite::Connection, sql: &str, params: &[&dyn rusqlite::types::ToSql]) -> Result<String, String> {
    let mut stmt = conn.prepare(sql).map_err(|e| e.to_string())?;
    let col_count = stmt.column_count();
    let col_names: Vec<String> = (0..col_count)
        .map(|i| stmt.column_name(i).unwrap_or("").to_string())
        .collect();

    let mut arr = Vec::new();
    let mut rows = stmt.query(params).map_err(|e| e.to_string())?;
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

#[tauri::command]
pub fn export_frames_csv(
    date: String,
    format: Option<String>,
    db: State<AppDb>,
) -> Result<String, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let start = format!("{date}T00:00:00");
    let end = format!("{date}T23:59:59");
    let fmt = format.unwrap_or_else(|| "csv".to_string());

    let sql = "SELECT * FROM frames WHERE timestamp BETWEEN ?1 AND ?2 ORDER BY timestamp";
    let params: &[&dyn rusqlite::types::ToSql] = &[&start, &end];

    if fmt == "json" {
        query_to_json(&conn, sql, params)
    } else {
        query_to_csv(&conn, sql, params)
    }
}

#[tauri::command]
pub fn export_summaries_csv(
    from: String,
    to: String,
    format: Option<String>,
    db: State<AppDb>,
) -> Result<String, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let start = format!("{from}T00:00:00");
    let end = format!("{to}T23:59:59");
    let fmt = format.unwrap_or_else(|| "csv".to_string());

    let sql = "SELECT * FROM summaries WHERE timestamp BETWEEN ?1 AND ?2 ORDER BY timestamp";
    let params: &[&dyn rusqlite::types::ToSql] = &[&start, &end];

    if fmt == "json" {
        query_to_json(&conn, sql, params)
    } else {
        query_to_csv(&conn, sql, params)
    }
}

#[tauri::command]
pub fn export_report(date: String, db: State<AppDb>) -> Result<String, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;

    let mut stmt = match conn.prepare("SELECT * FROM reports WHERE date = ?1") {
        Ok(s) => s,
        Err(_) => return Err("not found".to_string()),
    };

    let col_count = stmt.column_count();
    let col_names: Vec<String> = (0..col_count)
        .map(|i| stmt.column_name(i).unwrap_or("").to_string())
        .collect();

    let mut rows = stmt.query(rusqlite::params![date]).map_err(|e| e.to_string())?;

    if let Some(row) = rows.next().map_err(|e| e.to_string())? {
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
        serde_json::to_string_pretty(&serde_json::Value::Object(obj)).map_err(|e| e.to_string())
    } else {
        Err("not found".to_string())
    }
}
