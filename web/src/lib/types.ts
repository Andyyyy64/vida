export interface Frame {
  id: number;
  timestamp: string;
  path: string;
  screen_path: string;
  audio_path: string;
  transcription: string;
  brightness: number;
  motion_score: number;
  scene_type: 'dark' | 'normal' | 'bright';
  claude_description: string;
  activity: string;
  screen_extra_paths: string;
  foreground_window: string;
}

export interface AppStat {
  process: string;
  titleSample: string;
  durationSec: number;
  switchCount: number;
}

export interface Event {
  id: number;
  timestamp: string;
  event_type: string;
  description: string;
  frame_id: number;
}

export interface Summary {
  id: number;
  timestamp: string;
  scale: string;
  content: string;
  frame_count: number;
}

export interface DayStats {
  date: string;
  frames: number;
  events: number;
  summaries: number;
  avgMotion: number;
  avgBrightness: number;
  activity: number[];
}

export interface ActivityStat {
  activity: string;
  frameCount: number;
  durationSec: number;
}

export interface HourlyActivityStat {
  hour: number;
  activity: string;
  frameCount: number;
  durationSec: number;
}

export interface ActivityStats {
  activities: ActivityStat[];
  hourly: HourlyActivityStat[];
}

export interface SearchResults {
  frames: Frame[];
  summaries: Summary[];
}

export interface Session {
  activity: string;
  metaCategory: string;
  startTime: string;
  endTime: string;
  durationSec: number;
  frameCount: number;
}

export interface ActivityInfo {
  activity: string;
  metaCategory: string;
  frameCount: number;
}

export interface Report {
  id: number;
  date: string;
  content: string;
  generated_at: string;
  frame_count: number;
  focus_pct: number;
}

export interface Memo {
  date: string;
  content: string;
  updated_at: string | null;
}

export interface RangeDay {
  date: string;
  frameCount: number;
  totalSec: number;
  activities: Record<string, number>;
  metaCategories: Record<string, number>;
}

export interface ChatMessage {
  content: string;
  timestamp: string;
}

export interface ChatChannel {
  guild_id: string;
  guild_name: string;
  channel_id: string;
  channel_name: string;
  messages: ChatMessage[];
}

export interface ChatData {
  total: number;
  channels: ChatChannel[];
}

export interface RangeStats {
  from: string;
  to: string;
  frameDuration: number;
  totalFrames: number;
  totalSec: number;
  days: RangeDay[];
  activityTotals: Record<string, number>;
  metaTotals: Record<string, number>;
}
