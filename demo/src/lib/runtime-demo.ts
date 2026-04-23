import { useState, useEffect, useCallback } from 'react';
import type { Runtime } from '@web/lib/runtime';
import { DEMO_DATES } from './demo-fixtures';
import { createSimulator, DEMO_DAY_MINUTES } from './simulator';
import { demoSchedule } from './schedule';
import { buildFrameVirtualMinutes, formatDemoTimestamp } from './demo-timeline';
import { buildFrame, buildActivityMappings } from './mock-api';
import { createLiveFeedStore } from './live-feed-store';

const LOOP_DURATION_MS = 6 * 60 * 1000; // 6 minutes
const FRAME_INTERVAL_MINUTES = 5;
const INITIAL_VIRTUAL_MINUTES = 11 * 60 + 30; // Start around midday, awake at desk

const liveFeedStore = createLiveFeedStore();

const simulator = createSimulator({
  schedule: demoSchedule,
  loopDurationMs: LOOP_DURATION_MS,
  frameIntervalMinutes: FRAME_INTERVAL_MINUTES,
  initialVirtualMinutes: INITIAL_VIRTUAL_MINUTES,
});

const startTime = Date.now();

function elapsedMs() {
  return Date.now() - startTime;
}

function currentSnapshot() {
  return simulator.snapshotAtElapsedMs(elapsedMs());
}

function wrapVirtualMinutes(minutes: number) {
  return (minutes + DEMO_DAY_MINUTES) % DEMO_DAY_MINUTES;
}

function toAppName(windowTitle: string) {
  return windowTitle.split('|')[0] || 'system';
}

function generateEvents(frames: ReturnType<typeof buildFrame>[]) {
  const events: Array<{
    id: number;
    timestamp: string;
    event_type: string;
    description: string;
    frame_id: number;
  }> = [];

  for (let i = 1; i < frames.length; i++) {
    const previous = frames[i - 1];
    const current = frames[i];

    if (previous.activity !== current.activity) {
      events.push({
        id: events.length + 1,
        timestamp: current.timestamp,
        event_type: 'activity_change',
        description: `${previous.activity} -> ${current.activity}`,
        frame_id: current.id,
      });
    } else if (previous.foreground_window !== current.foreground_window && current.foreground_window) {
      events.push({
        id: events.length + 1,
        timestamp: current.timestamp,
        event_type: 'window_change',
        description: current.foreground_window,
        frame_id: current.id,
      });
    }
  }

  return events.slice(-24);
}

function summarizeFrames(frames: ReturnType<typeof buildFrame>[], scale: '10m' | '30m' | '1h' | '6h' | '24h') {
  const latest = frames.at(-1);
  if (!latest) {
    return {
      id: 1,
      timestamp: '2026-04-07T00:00:00.000Z',
      scale,
      content: 'Demo summary is warming up.',
      frame_count: 0,
    };
  }

  const durationMinutes = {
    '10m': 10,
    '30m': 30,
    '1h': 60,
    '6h': 360,
    '24h': 1440,
  }[scale];

  const latestTime = new Date(latest.timestamp).getTime();
  const cutoff = latestTime - durationMinutes * 60 * 1000;
  const recentFrames = frames.filter((frame) => new Date(frame.timestamp).getTime() >= cutoff);
  const activities = [...new Set(recentFrames.map((frame) => frame.activity))];
  const apps = [...new Set(recentFrames.map((frame) => toAppName(frame.foreground_window)).filter(Boolean))];

  return {
    id: durationMinutes,
    timestamp: latest.timestamp,
    scale,
    content: [
      `Current block: ${latest.activity}.`,
      activities.length > 1 ? `Recent changes: ${activities.slice(-3).join(', ')}.` : `Steady activity: ${latest.activity}.`,
      apps.length > 0 ? `Visible apps: ${apps.slice(0, 3).join(', ')}.` : 'No active desktop app was visible.',
    ].join(' '),
    frame_count: recentFrames.length,
  };
}

function createDemoSettings() {
  return {
    llm: {
      provider: 'gemini',
      gemini_model: 'gemini-3.1-flash-lite-preview',
      claude_model: 'haiku',
      codex_model: 'gpt-5.4',
    },
    capture: {
      device: 0,
      interval_sec: 30,
      audio_device: '',
    },
    presence: {
      enabled: true,
      sleep_start_hour: 23,
      sleep_end_hour: 8,
    },
    chat: {
      enabled: false,
      discord_enabled: false,
      discord_poll_interval: 60,
      discord_backfill_months: 3,
    },
    env: {},
    env_masked: {
      GEMINI_API_KEY: '********',
    },
  };
}

export function useDemoLiveFeed() {
  const [pose, setPose] = useState<'sleeping' | 'sitting_desk' | 'standing' | null>(null);
  const [hour, setHour] = useState(0);

  useEffect(() => {
    function tick() {
      const snap = currentSnapshot();
      setPose(snap.currentEntry.pose);
      setHour(snap.virtualMinutes / 60);
    }
    tick();
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, []);

  const setSnapshot = useCallback((dataUrl: string) => {
    liveFeedStore.setSnapshot(dataUrl);
  }, []);

  return { pose, hour, setSnapshot };
}

export function createDemoRuntime(): Runtime {
  function generateFrames(): ReturnType<typeof buildFrame>[] {
    const snap = currentSnapshot();
    const frameMinutes = buildFrameVirtualMinutes(snap.virtualMinutes, FRAME_INTERVAL_MINUTES);
    const frames: ReturnType<typeof buildFrame>[] = [];
    let lastVisibleActivity = 'programming';
    let lastVisibleWindow = 'code|VS Code - demo.ts';

    for (let i = 0; i < frameMinutes.length; i++) {
      const frameVirtualMinutes = frameMinutes[i];
      const entrySnap = simulator.snapshotAtElapsedMs(
        ((frameVirtualMinutes - INITIAL_VIRTUAL_MINUTES + DEMO_DAY_MINUTES) % DEMO_DAY_MINUTES / DEMO_DAY_MINUTES) * LOOP_DURATION_MS,
      );
      const ts = formatDemoTimestamp(frameVirtualMinutes);
      const foregroundWindow = entrySnap.currentEntry.window ?? '';

      if (foregroundWindow) {
        lastVisibleActivity = entrySnap.currentEntry.activity;
        lastVisibleWindow = foregroundWindow;
      }

      const screenActivity = entrySnap.currentEntry.presence
        ? entrySnap.currentEntry.activity
        : lastVisibleActivity;
      const screenWindow = entrySnap.currentEntry.presence
        ? foregroundWindow
        : lastVisibleWindow;

      frames.push(
        buildFrame(
          i + 1,
          ts,
          entrySnap.currentEntry.activity,
          entrySnap.currentEntry.description,
          foregroundWindow,
          screenActivity,
          screenWindow,
        ),
      );
    }
    return frames;
  }

  function generateStats(frames: ReturnType<typeof buildFrame>[]) {
    const avgBrightness = frames.length > 0
      ? frames.reduce((sum, frame) => sum + frame.brightness, 0) / frames.length
      : 0;
    const avgMotion = frames.length > 0
      ? frames.reduce((sum, frame) => sum + frame.motion_score, 0) / frames.length
      : 0;
    const events = generateEvents(frames);

    return {
      date: '2026-04-07',
      frames: frames.length,
      events: events.length,
      summaries: 5,
      avgMotion,
      avgBrightness,
      activity: Array.from({ length: 24 }, (_, hour) => frames.filter((frame) => new Date(frame.timestamp).getHours() === hour).length),
    };
  }

  return {
    api: {
      frames: {
        list: async () => generateFrames(),
        latest: async () => {
          const frames = generateFrames();
          return frames.length > 0 ? frames[frames.length - 1] : buildFrame(1, '2026-04-07T00:00:00.000', 'sleeping', 'Sleeping in a dark room.');
        },
        get: async (id) => {
          const frames = generateFrames();
          const frame = frames.find((f) => f.id === id);
          if (!frame) throw new Error('Frame not found');
          return frame;
        },
      },
      summaries: {
        list: async () => {
          const frames = generateFrames();
          return [
            summarizeFrames(frames, '24h'),
            summarizeFrames(frames, '6h'),
            summarizeFrames(frames, '1h'),
            summarizeFrames(frames, '30m'),
            summarizeFrames(frames, '10m'),
          ];
        },
      },
      events: {
        list: async () => {
          const frames = generateFrames();
          return generateEvents(frames);
        },
      },
      stats: {
        get: async () => generateStats(generateFrames()),
        dates: async () => DEMO_DATES,
        activities: async () => ({ activities: [], hourly: [] }),
        range: async () => ({
          from: DEMO_DATES[0],
          to: DEMO_DATES.at(-1)!,
          frameDuration: 30,
          totalFrames: 0,
          totalSec: 0,
          days: [],
          activityTotals: {},
          metaTotals: {},
        }),
        apps: async () => [],
      },
      sessions: async () => [],
      reports: {
        get: async () => {
          const frames = generateFrames();
          return {
          id: 1,
          date: '2026-04-07',
          content: summarizeFrames(frames, '24h').content,
          generated_at: '2026-04-07T23:59:00.000Z',
          frame_count: frames.length,
          focus_pct: 72,
          };
        },
        list: async () => [],
      },
      activities: {
        list: async () => [],
        mappings: async () => buildActivityMappings(),
      },
      memos: {
        get: async (date) => ({ date, content: 'Demo memo', updated_at: null }),
        put: async () => ({ ok: true }),
      },
      context: {
        get: async () => ({ content: 'Demo profile' }),
        put: async () => ({ ok: true }),
      },
      chat: async () => ({ total: 0, channels: [] }),
      status: async () => {
        const snap = currentSnapshot();
        return { running: true, camera: snap.currentEntry.presence, mic: snap.currentEntry.presence };
      },
      search: async () => {
        const frames = generateFrames();
        return {
          frames,
          summaries: [
            summarizeFrames(frames, '1h'),
            summarizeFrames(frames, '30m'),
            summarizeFrames(frames, '10m'),
          ],
        };
      },
      rag: {
        ask: async (query) => ({ response: `Demo answer: ${query}`, sources: [] }),
      },
      settings: {
        get: async () => createDemoSettings(),
        put: async () => ({ ok: true }),
        validateProvider: async () => ({ ok: true, code: 'ready' }),
      },
      devices: { get: async () => ({ cameras: [], audio: [] }) },
      data: {
        stats: async () => ({ dbSize: 0 }),
        exportTable: async (table) => `/exports/${table}.csv`,
      },
    },
    mediaUrl: (relativePath) => {
      const snapshot = liveFeedStore.getSnapshot();
      if (snapshot && relativePath.includes('camera-placeholder')) {
        return snapshot;
      }
      return relativePath;
    },
    liveFeed: {
      streamUrl: null,
      poseUrl: null,
      healthUrl: null,
      isLive: false,
    },
    init: async () => undefined,
    isDemo: true,
    getVirtualTime: () => {
      const snap = currentSnapshot();
      const normalizedMinutes = wrapVirtualMinutes(snap.virtualMinutes);
      const hours = Math.floor(normalizedMinutes / 60);
      const mins = Math.floor(normalizedMinutes % 60);
      const secs = Math.floor((normalizedMinutes % 1) * 60);
      const d = new Date(2026, 3, 7, hours, mins, secs);
      return d;
    },
  };
}
