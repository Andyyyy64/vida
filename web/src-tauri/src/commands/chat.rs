use crate::db::AppDb;
use crate::models::{ChatChannel, ChatData, ChatMessage};
use std::collections::HashMap;
use tauri::State;

#[tauri::command]
pub fn get_chat(date: String, db: State<AppDb>) -> Result<ChatData, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let start = format!("{date}T00:00:00");
    let end = format!("{date}T23:59:59");

    // The chat_messages table may not exist yet
    let mut stmt = match conn.prepare(
        "SELECT channel_id, channel_name, guild_id, guild_name,
                content, timestamp, author_name, is_self, metadata
         FROM chat_messages
         WHERE timestamp BETWEEN ?1 AND ?2 AND is_self = 1
         ORDER BY timestamp ASC",
    ) {
        Ok(s) => s,
        Err(_) => return Ok(ChatData::default()),
    };

    struct RawRow {
        channel_id: String,
        channel_name: String,
        guild_id: String,
        guild_name: String,
        content: String,
        timestamp: String,
    }

    let rows: Vec<RawRow> = stmt
        .query_map(rusqlite::params![start, end], |row| {
            Ok(RawRow {
                channel_id: row.get::<_, Option<String>>(0)?.unwrap_or_default(),
                channel_name: row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                guild_id: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
                guild_name: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                content: row.get::<_, Option<String>>(4)?.unwrap_or_default(),
                timestamp: row.get::<_, Option<String>>(5)?.unwrap_or_default(),
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    let total = rows.len();

    // Group by guild:channel
    let mut groups: HashMap<String, ChatChannel> = HashMap::new();
    let mut order: Vec<String> = Vec::new();

    for r in &rows {
        let key = format!(
            "{}:{}",
            if r.guild_id.is_empty() { "dm" } else { &r.guild_id },
            r.channel_id
        );

        let entry = groups.entry(key.clone()).or_insert_with(|| {
            order.push(key.clone());
            ChatChannel {
                guild_id: r.guild_id.clone(),
                guild_name: r.guild_name.clone(),
                channel_id: r.channel_id.clone(),
                channel_name: r.channel_name.clone(),
                messages: Vec::new(),
            }
        });

        entry.messages.push(ChatMessage {
            content: r.content.clone(),
            timestamp: r.timestamp.clone(),
        });
    }

    // Sort by first message time
    let mut channels: Vec<ChatChannel> = order
        .into_iter()
        .filter_map(|k| groups.remove(&k))
        .collect();

    channels.sort_by(|a, b| {
        let a_ts = a.messages.first().map(|m| m.timestamp.as_str()).unwrap_or("");
        let b_ts = b.messages.first().map(|m| m.timestamp.as_str()).unwrap_or("");
        a_ts.cmp(b_ts)
    });

    Ok(ChatData { total, channels })
}
