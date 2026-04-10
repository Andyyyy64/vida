import type { Frame, DayStats } from '../src/lib/types';

export function makeFrame(id: number, timestamp: string, extras: Partial<Frame> = {}): Frame {
  return {
    id,
    timestamp,
    path: `frames/${id}.jpg`,
    screen_path: `screens/${id}.png`,
    audio_path: '',
    transcription: '',
    brightness: 128,
    motion_score: 0.1,
    scene_type: 'normal',
    claude_description: `Description for frame ${id}`,
    activity: 'コーディング',
    screen_extra_paths: '',
    foreground_window: 'Code.exe||main.ts - vida',
    ...extras,
  };
}

export function makeDayStats(date: string, frameCount: number, activity?: number[]): DayStats {
  return {
    date,
    frames: frameCount,
    events: 0,
    summaries: 0,
    avgMotion: 0.1,
    avgBrightness: 128,
    activity: activity ?? Array.from({ length: 24 }, (_, h) => (h >= 9 && h <= 17 ? 10 : 0)),
  };
}

/** Build a timestamp like "2026-04-10T09:30:00" for a given hour/minute. */
export function ts(date: string, hour: number, minute = 0): string {
  return `${date}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`;
}
