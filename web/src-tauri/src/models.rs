use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ── Core data models ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Frame {
    pub id: i64,
    pub timestamp: String,
    #[serde(default)]
    pub path: String,
    #[serde(default)]
    pub screen_path: String,
    #[serde(default)]
    pub audio_path: String,
    #[serde(default)]
    pub transcription: String,
    #[serde(default)]
    pub brightness: f64,
    #[serde(default)]
    pub motion_score: f64,
    #[serde(default)]
    pub scene_type: String,
    #[serde(default)]
    pub claude_description: String,
    #[serde(default)]
    pub activity: String,
    #[serde(default)]
    pub screen_extra_paths: String,
    #[serde(default)]
    pub foreground_window: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Summary {
    pub id: i64,
    pub timestamp: String,
    pub scale: String,
    #[serde(default)]
    pub content: String,
    #[serde(default)]
    pub frame_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Event {
    pub id: i64,
    pub timestamp: String,
    pub event_type: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub frame_id: Option<i64>,
}

// ── Stats models ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct DayStats {
    pub date: String,
    pub frames: i64,
    pub events: i64,
    pub summaries: i64,
    pub avg_motion: f64,
    pub avg_brightness: f64,
    pub activity: Vec<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ActivityStat {
    pub activity: String,
    pub frame_count: i64,
    pub duration_sec: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct HourlyActivityStat {
    pub hour: i64,
    pub activity: String,
    pub frame_count: i64,
    pub duration_sec: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ActivityStats {
    pub activities: Vec<ActivityStat>,
    pub hourly: Vec<HourlyActivityStat>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct AppStat {
    pub process: String,
    pub title_sample: String,
    pub duration_sec: i64,
    pub switch_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct Session {
    pub activity: String,
    pub meta_category: String,
    pub start_time: String,
    pub end_time: String,
    pub duration_sec: i64,
    pub frame_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ActivityInfo {
    pub activity: String,
    pub meta_category: String,
    pub frame_count: i64,
}

// ── Reports and Memos ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Report {
    pub id: i64,
    pub date: String,
    #[serde(default)]
    pub content: String,
    pub generated_at: String,
    #[serde(default)]
    pub frame_count: i64,
    #[serde(default)]
    pub focus_pct: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Memo {
    pub date: String,
    #[serde(default)]
    pub content: String,
    pub updated_at: Option<String>,
}

// ── Search ──────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SearchResults {
    pub frames: Vec<Frame>,
    pub summaries: Vec<Summary>,
}

// ── Chat ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ChatMessage {
    pub content: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ChatChannel {
    pub guild_id: String,
    pub guild_name: String,
    pub channel_id: String,
    pub channel_name: String,
    pub messages: Vec<ChatMessage>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ChatData {
    pub total: usize,
    pub channels: Vec<ChatChannel>,
}

// ── Range Stats ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct RangeDay {
    pub date: String,
    pub frame_count: i64,
    pub total_sec: i64,
    pub activities: HashMap<String, i64>,
    pub meta_categories: HashMap<String, i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct RangeStats {
    pub from: String,
    pub to: String,
    pub frame_duration: i64,
    pub total_frames: i64,
    pub total_sec: i64,
    pub days: Vec<RangeDay>,
    pub activity_totals: HashMap<String, i64>,
    pub meta_totals: HashMap<String, i64>,
}

// ── Data management ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct DataStats {
    pub counts: HashMap<String, i64>,
    pub first_date: String,
    pub last_date: String,
    pub db_size_bytes: u64,
}

// ── Settings ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct LlmSettings {
    pub provider: String,
    pub gemini_model: String,
    pub claude_model: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CaptureSettings {
    pub device: i64,
    pub interval_sec: i64,
    #[serde(default)]
    pub audio_device: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PresenceSettings {
    pub enabled: bool,
    pub sleep_start_hour: i64,
    pub sleep_end_hour: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ChatSettings {
    pub enabled: bool,
    pub discord_enabled: bool,
    pub discord_poll_interval: i64,
    pub discord_backfill_months: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SettingsPayload {
    pub llm: LlmSettings,
    pub capture: CaptureSettings,
    pub presence: PresenceSettings,
    pub chat: ChatSettings,
    #[serde(default)]
    pub env: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SettingsResponse {
    #[serde(flatten)]
    pub settings: SettingsPayload,
    pub env_masked: HashMap<String, String>,
}

// ── Devices ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CameraDevice {
    pub index: i64,
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AudioDevice {
    pub id: String,
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DeviceResult {
    pub cameras: Vec<CameraDevice>,
    pub audio: Vec<AudioDevice>,
}
