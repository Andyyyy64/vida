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

fn s_str(settings: &HashMap<String, String>, key: &str, default: &str) -> String {
    settings.get(key).cloned().unwrap_or_else(|| default.to_string())
}

fn s_i64(settings: &HashMap<String, String>, key: &str, default: i64) -> i64 {
    settings
        .get(key)
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn s_bool(settings: &HashMap<String, String>, key: &str, default: bool) -> bool {
    settings
        .get(key)
        .map(|v| v == "true")
        .unwrap_or(default)
}

#[tauri::command]
pub fn get_settings(db: State<AppDb>) -> Result<serde_json::Value, String> {
    let s = db.get_all_settings();

    let mut env = serde_json::Map::new();
    let mut env_masked = serde_json::Map::new();
    for key in ENV_KEYS {
        let val = s_str(&s, &format!("env.{key}"), "");
        env.insert((*key).to_string(), serde_json::Value::String(String::new()));
        env_masked.insert(
            (*key).to_string(),
            serde_json::Value::String(mask_secret(&val)),
        );
    }

    Ok(serde_json::json!({
        "llm": {
            "provider": s_str(&s, "llm.provider", "gemini"),
            "gemini_model": s_str(&s, "llm.gemini_model", "gemini-3.1-flash-lite-preview"),
            "claude_model": s_str(&s, "llm.claude_model", "haiku"),
        },
        "capture": {
            "device": s_i64(&s, "capture.device", 0),
            "interval_sec": s_i64(&s, "capture.interval_sec", 30),
            "audio_device": s_str(&s, "capture.audio_device", ""),
        },
        "presence": {
            "enabled": s_bool(&s, "presence.enabled", true),
            "sleep_start_hour": s_i64(&s, "presence.sleep_start_hour", 23),
            "sleep_end_hour": s_i64(&s, "presence.sleep_end_hour", 8),
        },
        "chat": {
            "enabled": s_bool(&s, "chat.enabled", false),
            "discord_enabled": s_bool(&s, "chat.discord.enabled", false),
            "discord_poll_interval": s_i64(&s, "chat.discord.poll_interval", 60),
            "discord_backfill_months": s_i64(&s, "chat.discord.backfill_months", 3),
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
    let current = db.get_all_settings();

    // Helper closures to get values from body or fall back to current DB value
    let body_str = |section: &str, key: &str, db_key: &str, default: &str| -> String {
        body.get(section)
            .and_then(|s| s.get(key))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| s_str(&current, db_key, default))
    };

    let body_i64 = |section: &str, key: &str, db_key: &str, default: i64| -> i64 {
        body.get(section)
            .and_then(|s| s.get(key))
            .and_then(|v| v.as_i64())
            .unwrap_or_else(|| s_i64(&current, db_key, default))
    };

    let body_bool = |section: &str, key: &str, db_key: &str, default: bool| -> bool {
        body.get(section)
            .and_then(|s| s.get(key))
            .and_then(|v| v.as_bool())
            .unwrap_or_else(|| s_bool(&current, db_key, default))
    };

    // Validate
    let provider = body_str("llm", "provider", "llm.provider", "gemini");
    if provider != "gemini" && provider != "claude" {
        return Err("Invalid LLM provider".to_string());
    }

    let interval_sec = body_i64("capture", "interval_sec", "capture.interval_sec", 30);
    if !(5..=3600).contains(&interval_sec) {
        return Err("Capture interval must be 5-3600 seconds".to_string());
    }

    let device = body_i64("capture", "device", "capture.device", 0);
    if device < 0 {
        return Err("Camera device must be >= 0".to_string());
    }

    let sleep_start = body_i64("presence", "sleep_start_hour", "presence.sleep_start_hour", 23);
    if !(0..=23).contains(&sleep_start) {
        return Err("Sleep start hour must be 0-23".to_string());
    }

    let sleep_end = body_i64("presence", "sleep_end_hour", "presence.sleep_end_hour", 8);
    if !(0..=23).contains(&sleep_end) {
        return Err("Sleep end hour must be 0-23".to_string());
    }

    let discord_poll = body_i64("chat", "discord_poll_interval", "chat.discord.poll_interval", 60);
    if discord_poll < 10 {
        return Err("Discord poll interval must be >= 10 seconds".to_string());
    }

    let gemini_model = body_str("llm", "gemini_model", "llm.gemini_model", "gemini-3.1-flash-lite-preview");
    let claude_model = body_str("llm", "claude_model", "llm.claude_model", "haiku");
    let audio_device = body_str("capture", "audio_device", "capture.audio_device", "");
    let presence_enabled = body_bool("presence", "enabled", "presence.enabled", true);
    let chat_enabled = body_bool("chat", "enabled", "chat.enabled", false);
    let discord_enabled = body_bool("chat", "discord_enabled", "chat.discord.enabled", false);
    let discord_backfill = body_i64("chat", "discord_backfill_months", "chat.discord.backfill_months", 3);

    let mut entries = HashMap::new();
    entries.insert("llm.provider".to_string(), provider);
    entries.insert("llm.gemini_model".to_string(), gemini_model);
    entries.insert("llm.claude_model".to_string(), claude_model);
    entries.insert("capture.device".to_string(), device.to_string());
    entries.insert("capture.interval_sec".to_string(), interval_sec.to_string());
    entries.insert("capture.audio_device".to_string(), audio_device);
    entries.insert("presence.enabled".to_string(), presence_enabled.to_string());
    entries.insert("presence.sleep_start_hour".to_string(), sleep_start.to_string());
    entries.insert("presence.sleep_end_hour".to_string(), sleep_end.to_string());
    entries.insert("chat.enabled".to_string(), chat_enabled.to_string());
    entries.insert("chat.discord.enabled".to_string(), discord_enabled.to_string());
    entries.insert("chat.discord.poll_interval".to_string(), discord_poll.to_string());
    entries.insert("chat.discord.backfill_months".to_string(), discord_backfill.to_string());

    // Env keys — only update if user provided a real (non-masked) value.
    // We iterate the ALLOW-LISTED keys, never the user's map, so arbitrary
    // environment variable names can't be smuggled into the settings table.
    // Reject values containing control characters to prevent newline
    // injection if the value is ever exported as a real env var.
    if let Some(env_obj) = body.get("env").and_then(|v| v.as_object()) {
        for key in ENV_KEYS {
            if let Some(val) = env_obj.get(*key).and_then(|v| v.as_str()) {
                if val.starts_with("••••") {
                    continue; // Masked placeholder — don't overwrite
                }
                if val.len() > 4096 {
                    return Err(format!("{key}: value too long"));
                }
                if val.chars().any(|c| c == '\n' || c == '\r' || c == '\0') {
                    return Err(format!("{key}: invalid characters"));
                }
                entries.insert(format!("env.{key}"), val.to_string());
            }
        }
    }

    db.put_settings(&entries)?;

    Ok(serde_json::json!({"ok": true}))
}
