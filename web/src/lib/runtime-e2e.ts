import type {
  ActivityInfo,
  ActivityStats,
  AppStat,
  ChatData,
  DayStats,
  Event,
  Frame,
  Memo,
  RangeStats,
  Report,
  SearchResults,
  Session,
  Summary,
} from './types';
import type { Runtime, RuntimeApi } from './runtime';

export interface E2EState {
  frames: Record<string, Frame[]>;
  summaries: Record<string, Summary[]>;
  events: Record<string, Event[]>;
  stats: Record<string, DayStats>;
  dates: string[];
  activities: Record<string, ActivityStats>;
  range: RangeStats | null;
  apps: Record<string, AppStat[]>;
  sessions: Record<string, Session[]>;
  reports: Record<string, Report>;
  reportsList: Report[];
  activityList: ActivityInfo[];
  mappings: Record<string, string>;
  memos: Record<string, Memo>;
  context: string;
  chat: Record<string, ChatData>;
  status: { running: boolean; camera: boolean; mic: boolean };
  search: SearchResults;
  rag: { response: string; sources: { type: string; timestamp: string; preview: string; distance: number }[] };
  settings: Record<string, unknown>;
  providerValidation: { ok: boolean; code: string; detail?: string };
  devices: unknown;
  dataStats: unknown;
  liveFeed: { isLive: boolean; streamUrl: string | null; poseUrl: string | null; healthUrl: string | null };
}

export interface E2EWrites {
  frames: { id: number; patch: unknown }[];
  memos: { date: string; content: string }[];
  context: string[];
  settings: unknown[];
}

declare global {
  interface Window {
    __E2E__?: boolean;
    __E2E_STATE__?: Partial<E2EState>;
    __E2E_WRITES__?: E2EWrites;
  }
}

function defaultState(): E2EState {
  return {
    frames: {},
    summaries: {},
    events: {},
    stats: {},
    dates: [],
    activities: {},
    range: null,
    apps: {},
    sessions: {},
    reports: {},
    reportsList: [],
    activityList: [],
    mappings: {},
    memos: {},
    context: '',
    chat: {},
    status: { running: true, camera: true, mic: true },
    search: { frames: [], summaries: [] },
    rag: { response: '', sources: [] },
    settings: {},
    providerValidation: { ok: true, code: 'ready' },
    devices: { cameras: [], microphones: [] },
    dataStats: { total_frames: 0, total_events: 0, total_summaries: 0 },
    liveFeed: { isLive: false, streamUrl: null, poseUrl: null, healthUrl: null },
  };
}

function mergeState(): E2EState {
  const base = defaultState();
  const override = (typeof window !== 'undefined' && window.__E2E_STATE__) || {};
  return { ...base, ...override } as E2EState;
}

function ensureWrites(): E2EWrites {
  if (typeof window === 'undefined') return { frames: [], memos: [], context: [], settings: [] };
  if (!window.__E2E_WRITES__) {
    window.__E2E_WRITES__ = { frames: [], memos: [], context: [], settings: [] };
  }
  return window.__E2E_WRITES__;
}

function todayIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function createApi(): RuntimeApi {
  const get = <K extends keyof E2EState>(key: K): E2EState[K] => mergeState()[key];

  return {
    frames: {
      list: async (date) => get('frames')[date] ?? [],
      latest: async () => {
        const all = Object.values(get('frames')).flat();
        if (all.length === 0) throw new Error('no frames');
        return all[all.length - 1];
      },
      get: async (id) => {
        const all = Object.values(get('frames')).flat();
        const f = all.find((x) => x.id === id);
        if (!f) throw new Error(`frame ${id} not found`);
        return f;
      },
    },
    summaries: {
      list: async (date) => get('summaries')[date] ?? [],
    },
    events: {
      list: async (date) => get('events')[date] ?? [],
    },
    stats: {
      get: async (date) =>
        get('stats')[date] ?? {
          date,
          frames: 0,
          events: 0,
          summaries: 0,
          avgMotion: 0,
          avgBrightness: 0,
          activity: [],
        },
      dates: async () => {
        const list = get('dates');
        return list.length > 0 ? list : [todayIso()];
      },
      activities: async (date) => get('activities')[date] ?? { activities: [], hourly: [] },
      range: async (from, to) =>
        get('range') ?? {
          from,
          to,
          frameDuration: 30,
          totalFrames: 0,
          totalSec: 0,
          days: [],
          activityTotals: {},
          metaTotals: {},
        },
      apps: async (date) => get('apps')[date] ?? [],
    },
    sessions: async (date) => get('sessions')[date] ?? [],
    reports: {
      get: async (date) =>
        get('reports')[date] ?? {
          id: 0,
          date,
          content: '',
          generated_at: '',
          frame_count: 0,
          focus_pct: 0,
        },
      list: async () => get('reportsList'),
    },
    activities: {
      list: async () => get('activityList'),
      mappings: async () => get('mappings'),
    },
    memos: {
      get: async (date) => get('memos')[date] ?? { date, content: '', updated_at: null },
      put: async (date, content) => {
        ensureWrites().memos.push({ date, content });
        return { ok: true };
      },
    },
    context: {
      get: async () => ({ content: get('context') }),
      put: async (content) => {
        ensureWrites().context.push(content);
        return { ok: true };
      },
    },
    chat: async (date) => get('chat')[date] ?? { total: 0, channels: [] },
    status: async () => get('status'),
    search: async () => get('search'),
    rag: {
      ask: async () => get('rag'),
    },
    settings: {
      get: async () => get('settings'),
      put: async (body) => {
        ensureWrites().settings.push(body);
        return body;
      },
      validateProvider: async () => get('providerValidation'),
    },
    devices: {
      get: async () => get('devices'),
    },
    data: {
      stats: async () => get('dataStats'),
      exportTable: async () => '',
    },
  };
}

export function createE2ERuntime(): Runtime {
  const api = createApi();
  const lf = mergeState().liveFeed;
  return {
    api,
    mediaUrl: (relativePath) => `/__e2e_media__/${relativePath}`,
    liveFeed: {
      isLive: lf.isLive,
      streamUrl: lf.streamUrl,
      poseUrl: lf.poseUrl,
      healthUrl: lf.healthUrl,
    },
    init: async () => {},
    isDemo: false,
  };
}
