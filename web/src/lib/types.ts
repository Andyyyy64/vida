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
