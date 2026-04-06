use crate::db::AppDb;
use std::collections::HashMap;
use tauri::State;

const ENV_KEYS: &[&str] = &[
    "GEMINI_API_KEY",
    "DISCORD_USER_TOKEN",
    "DISCORD_USER_ID",
    "NOTIFY_WEBHOOK_URL",
];

fn mask_secret(val: &str) -> String {
    if val.is_empty() {
        return String::new();
    }
    if val.len() <= 4 {
        return "••••".to_string();
    }
    format!("••••{}", &val[val.len() - 4..])
}

fn read_env(env_path: &std::path::Path) -> HashMap<String, String> {
    let mut result = HashMap::new();
    let content = match std::fs::read_to_string(env_path) {
        Ok(c) => c,
        Err(_) => return result,
    };
    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        if let Some(eq) = trimmed.find('=') {
            let key = trimmed[..eq].trim().to_string();
            let val = trimmed[eq + 1..]
                .trim()
                .trim_matches('"')
                .trim_matches('\'')
                .to_string();
            result.insert(key, val);
        }
    }
    result
}

fn write_env(env_path: &std::path::Path, updates: &HashMap<String, String>) {
    // Read existing content to preserve unknown keys and comments
    let existing: Vec<String> = std::fs::read_to_string(env_path)
        .unwrap_or_default()
        .lines()
        .map(|l| l.to_string())
        .collect();

    let mut written = std::collections::HashSet::new();
    let mut output = Vec::new();

    for line in &existing {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            output.push(line.clone());
            continue;
        }
        if let Some(eq) = trimmed.find('=') {
            let key = trimmed[..eq].trim();
            if let Some(val) = updates.get(key) {
                if !val.is_empty() {
                    output.push(format!("{key}={val}"));
                }
                written.insert(key.to_string());
            } else {
                output.push(line.clone());
            }
        } else {
            output.push(line.clone());
        }
    }

    // Append new keys not already in the file
    for (key, val) in updates {
        if !written.contains(key.as_str()) && !val.is_empty() {
            output.push(format!("{key}={val}"));
        }
    }

    let content = output.join("\n").trim_end().to_string();
    let final_content = if content.is_empty() {
        String::new()
    } else {
        format!("{content}\n")
    };
    let _ = std::fs::write(env_path, final_content);
}

fn toml_str(v: &str) -> String {
    format!("\"{}\"", v.replace('\\', "\\\\").replace('"', "\\\""))
}

#[tauri::command]
pub fn get_settings(db: State<AppDb>) -> Result<serde_json::Value, String> {
    let toml_path = db.config_dir.join("life.toml");
    let env_path = db.config_dir.join(".env");

    // Read TOML
    let toml_content = std::fs::read_to_string(&toml_path).unwrap_or_default();
    let toml_val: toml::Value = toml::from_str(&toml_content).unwrap_or(toml::Value::Table(toml::map::Map::new()));

    let llm = toml_val.get("llm").and_then(|v| v.as_table());
    let capture = toml_val.get("capture").and_then(|v| v.as_table());
    let presence = toml_val.get("presence").and_then(|v| v.as_table());
    let chat = toml_val.get("chat").and_then(|v| v.as_table());
    let discord = chat
        .and_then(|c| c.get("discord"))
        .and_then(|v| v.as_table());

    fn str_val(table: Option<&toml::map::Map<String, toml::Value>>, key: &str, default: &str) -> String {
        table
            .and_then(|t| t.get(key))
            .and_then(|v| v.as_str())
            .unwrap_or(default)
            .to_string()
    }

    fn int_val(table: Option<&toml::map::Map<String, toml::Value>>, key: &str, default: i64) -> i64 {
        table
            .and_then(|t| t.get(key))
            .and_then(|v| v.as_integer())
            .unwrap_or(default)
    }

    fn bool_val(table: Option<&toml::map::Map<String, toml::Value>>, key: &str, default: bool) -> bool {
        table
            .and_then(|t| t.get(key))
            .and_then(|v| v.as_bool())
            .unwrap_or(default)
    }

    // Read .env
    let env_vars = read_env(&env_path);

    let mut env = serde_json::Map::new();
    let mut env_masked = serde_json::Map::new();
    for key in ENV_KEYS {
        let val = env_vars.get(*key).cloned().unwrap_or_default();
        env.insert((*key).to_string(), serde_json::Value::String(String::new()));
        env_masked.insert(
            (*key).to_string(),
            serde_json::Value::String(mask_secret(&val)),
        );
    }

    Ok(serde_json::json!({
        "llm": {
            "provider": str_val(llm, "provider", "gemini"),
            "gemini_model": str_val(llm, "gemini_model", "gemini-3.1-flash-lite-preview"),
            "claude_model": str_val(llm, "claude_model", "haiku"),
        },
        "capture": {
            "device": int_val(capture, "device", 0),
            "interval_sec": int_val(capture, "interval_sec", 30),
            "audio_device": str_val(capture, "audio_device", ""),
        },
        "presence": {
            "enabled": bool_val(presence, "enabled", true),
            "sleep_start_hour": int_val(presence, "sleep_start_hour", 23),
            "sleep_end_hour": int_val(presence, "sleep_end_hour", 8),
        },
        "chat": {
            "enabled": bool_val(chat, "enabled", false),
            "discord_enabled": bool_val(discord, "enabled", false),
            "discord_poll_interval": int_val(discord, "poll_interval", 60),
            "discord_backfill_months": int_val(discord, "backfill_months", 3),
        },
        "env": env,
        "env_masked": env_masked,
    }))
}

#[tauri::command]
pub fn put_settings(
    body: serde_json::Value,
    db: State<AppDb>,
) -> Result<serde_json::Value, String> {
    let toml_path = db.config_dir.join("life.toml");
    let env_path = db.config_dir.join(".env");

    // Read current TOML for merging
    let toml_content = std::fs::read_to_string(&toml_path).unwrap_or_default();
    let current: toml::Value =
        toml::from_str(&toml_content).unwrap_or(toml::Value::Table(toml::map::Map::new()));

    let cur_llm = current.get("llm").and_then(|v| v.as_table());
    let cur_capture = current.get("capture").and_then(|v| v.as_table());
    let cur_presence = current.get("presence").and_then(|v| v.as_table());
    let cur_chat = current.get("chat").and_then(|v| v.as_table());
    let cur_discord = cur_chat
        .and_then(|c| c.get("discord"))
        .and_then(|v| v.as_table());

    // Helper closures to get values from body or fall back to current
    let body_str = |section: &str, key: &str, cur_table: Option<&toml::map::Map<String, toml::Value>>, default: &str| -> String {
        body.get(section)
            .and_then(|s| s.get(key))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| {
                cur_table
                    .and_then(|t| t.get(key))
                    .and_then(|v| v.as_str())
                    .unwrap_or(default)
                    .to_string()
            })
    };

    let body_i64 = |section: &str, key: &str, cur_table: Option<&toml::map::Map<String, toml::Value>>, default: i64| -> i64 {
        body.get(section)
            .and_then(|s| s.get(key))
            .and_then(|v| v.as_i64())
            .unwrap_or_else(|| {
                cur_table
                    .and_then(|t| t.get(key))
                    .and_then(|v| v.as_integer())
                    .unwrap_or(default)
            })
    };

    let body_bool = |section: &str, key: &str, cur_table: Option<&toml::map::Map<String, toml::Value>>, default: bool| -> bool {
        body.get(section)
            .and_then(|s| s.get(key))
            .and_then(|v| v.as_bool())
            .unwrap_or_else(|| {
                cur_table
                    .and_then(|t| t.get(key))
                    .and_then(|v| v.as_bool())
                    .unwrap_or(default)
            })
    };

    // Validate
    let provider = body_str("llm", "provider", cur_llm, "gemini");
    if provider != "gemini" && provider != "claude" {
        return Err("Invalid LLM provider".to_string());
    }

    let interval_sec = body_i64("capture", "interval_sec", cur_capture, 30);
    if interval_sec < 5 || interval_sec > 3600 {
        return Err("Capture interval must be 5-3600 seconds".to_string());
    }

    let device = body_i64("capture", "device", cur_capture, 0);
    if device < 0 {
        return Err("Camera device must be >= 0".to_string());
    }

    let sleep_start = body_i64("presence", "sleep_start_hour", cur_presence, 23);
    if sleep_start < 0 || sleep_start > 23 {
        return Err("Sleep start hour must be 0-23".to_string());
    }

    let sleep_end = body_i64("presence", "sleep_end_hour", cur_presence, 8);
    if sleep_end < 0 || sleep_end > 23 {
        return Err("Sleep end hour must be 0-23".to_string());
    }

    let discord_poll = body_i64("chat", "discord_poll_interval", cur_discord, 60);
    if discord_poll < 10 {
        return Err("Discord poll interval must be >= 10 seconds".to_string());
    }

    let gemini_model = body_str("llm", "gemini_model", cur_llm, "gemini-3.1-flash-lite-preview");
    let claude_model = body_str("llm", "claude_model", cur_llm, "haiku");
    let audio_device = body_str("capture", "audio_device", cur_capture, "");
    let presence_enabled = body_bool("presence", "enabled", cur_presence, true);
    let chat_enabled = body_bool("chat", "enabled", cur_chat, false);
    let discord_enabled = body_bool("chat", "discord_enabled", cur_discord, false);
    let discord_backfill = body_i64("chat", "discord_backfill_months", cur_discord, 3);

    // Build TOML string
    let mut lines = Vec::new();
    lines.push("[llm]".to_string());
    lines.push(format!("provider = {}", toml_str(&provider)));
    lines.push(format!("gemini_model = {}", toml_str(&gemini_model)));
    lines.push(format!("claude_model = {}", toml_str(&claude_model)));
    lines.push(String::new());
    lines.push("[capture]".to_string());
    lines.push(format!("device = {device}"));
    lines.push(format!("interval_sec = {interval_sec}"));
    if !audio_device.is_empty() {
        lines.push(format!("audio_device = {}", toml_str(&audio_device)));
    }
    lines.push(String::new());
    lines.push("[presence]".to_string());
    lines.push(format!("enabled = {}", if presence_enabled { "true" } else { "false" }));
    lines.push(format!("sleep_start_hour = {sleep_start}"));
    lines.push(format!("sleep_end_hour = {sleep_end}"));
    lines.push(String::new());
    lines.push("[chat]".to_string());
    lines.push(format!("enabled = {}", if chat_enabled { "true" } else { "false" }));
    lines.push(String::new());
    lines.push("[chat.discord]".to_string());
    lines.push(format!("enabled = {}", if discord_enabled { "true" } else { "false" }));
    lines.push(format!("poll_interval = {discord_poll}"));
    lines.push(format!("backfill_months = {discord_backfill}"));
    lines.push(String::new());

    let toml_output = lines.join("\n");
    std::fs::write(&toml_path, &toml_output)
        .map_err(|e| format!("Failed to write life.toml: {e}"))?;

    // Write .env — only update keys that were provided and non-masked
    let mut env_updates: HashMap<String, String> = HashMap::new();
    if let Some(env_obj) = body.get("env").and_then(|v| v.as_object()) {
        for key in ENV_KEYS {
            if let Some(val) = env_obj.get(*key).and_then(|v| v.as_str()) {
                // Skip if still the masked placeholder
                if val.starts_with("••••") {
                    continue;
                }
                env_updates.insert((*key).to_string(), val.to_string());
            }
        }
    }
    write_env(&env_path, &env_updates);

    Ok(serde_json::json!({"ok": true}))
}
