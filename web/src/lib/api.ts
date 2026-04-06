import type {
  Frame,
  Event,
  Summary,
  DayStats,
  ActivityStats,
  SearchResults,
  Session,
  ActivityInfo,
  RangeStats,
  Report,
  AppStat,
  Memo,
  ChatData,
} from './types';

// ---------------------------------------------------------------------------
// Environment detection
// ---------------------------------------------------------------------------

const IS_TAURI = !!(window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__;

// Lazy-load invoke so non-Tauri builds don't fail
let _invoke: ((cmd: string, args?: Record<string, unknown>) => Promise<unknown>) | null = null;

async function tauriInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (!_invoke) {
    const mod = await import('@tauri-apps/api/core');
    _invoke = mod.invoke;
  }
  return _invoke(cmd, args) as Promise<T>;
}

// ---------------------------------------------------------------------------
// Fetch helpers (browser / dev mode)
// ---------------------------------------------------------------------------

const BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE}${url}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function putJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function fetchText(url: string): Promise<string> {
  const res = await fetch(`${BASE}${url}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.text();
}

// ---------------------------------------------------------------------------
// Dual-mode API
// ---------------------------------------------------------------------------

export const api = {
  frames: {
    list: (date: string): Promise<Frame[]> =>
      IS_TAURI
        ? tauriInvoke('get_frames', { date })
        : fetchJson(`/frames?date=${date}`),

    latest: (): Promise<Frame> =>
      IS_TAURI
        ? tauriInvoke<Frame | null>('get_latest_frame').then((f) => {
            if (!f) throw new Error('No frames');
            return f;
          })
        : fetchJson('/frames/latest'),

    get: (id: number): Promise<Frame> =>
      IS_TAURI
        ? tauriInvoke<Frame | null>('get_frame', { id }).then((f) => {
            if (!f) throw new Error('Frame not found');
            return f;
          })
        : fetchJson(`/frames/${id}`),
  },

  summaries: {
    list: (date: string, scale?: string): Promise<Summary[]> =>
      IS_TAURI
        ? tauriInvoke('get_summaries', { date, scale: scale ?? null })
        : fetchJson(`/summaries?date=${date}${scale ? `&scale=${scale}` : ''}`),
  },

  events: {
    list: (date: string): Promise<Event[]> =>
      IS_TAURI
        ? tauriInvoke('get_events', { date })
        : fetchJson(`/events?date=${date}`),
  },

  stats: {
    get: (date: string): Promise<DayStats> =>
      IS_TAURI
        ? tauriInvoke('get_stats', { date })
        : fetchJson(`/stats?date=${date}`),

    dates: (): Promise<string[]> =>
      IS_TAURI
        ? tauriInvoke('get_dates')
        : fetchJson('/stats/dates'),

    activities: (date: string): Promise<ActivityStats> =>
      IS_TAURI
        ? tauriInvoke('get_activities', { date })
        : fetchJson(`/stats/activities?date=${date}`),

    range: (from: string, to: string): Promise<RangeStats> =>
      IS_TAURI
        ? tauriInvoke('get_range_stats', { from, to })
        : fetchJson(`/stats/range?from=${from}&to=${to}`),

    apps: (date: string): Promise<AppStat[]> =>
      IS_TAURI
        ? tauriInvoke('get_apps', { date })
        : fetchJson(`/stats/apps?date=${date}`),
  },

  sessions: (date: string): Promise<Session[]> =>
    IS_TAURI
      ? tauriInvoke('get_sessions', { date })
      : fetchJson(`/sessions?date=${date}`),

  reports: {
    get: (date: string): Promise<Report> =>
      IS_TAURI
        ? tauriInvoke<Report | null>('get_report', { date }).then((r) => {
            if (!r) throw new Error('Report not found');
            return r;
          })
        : fetchJson(`/reports?date=${date}`),

    list: (): Promise<Report[]> =>
      IS_TAURI
        ? tauriInvoke('list_reports')
        : fetchJson('/reports'),
  },

  activities: {
    list: (): Promise<ActivityInfo[]> =>
      IS_TAURI
        ? tauriInvoke('list_activities')
        : fetchJson('/activities'),

    mappings: (): Promise<Record<string, string>> =>
      IS_TAURI
        ? tauriInvoke('get_activity_mappings')
        : fetchJson('/activities/mappings'),
  },

  memos: {
    get: (date: string): Promise<Memo> =>
      IS_TAURI
        ? tauriInvoke<Memo | null>('get_memo', { date }).then((m) => m ?? { date, content: '', updated_at: null })
        : fetchJson(`/memos?date=${date}`),

    put: (date: string, content: string): Promise<{ ok: boolean }> =>
      IS_TAURI
        ? tauriInvoke<Memo>('put_memo', { date, content }).then(() => ({ ok: true }))
        : putJson('/memos', { date, content }),
  },

  context: {
    get: (): Promise<{ content: string }> =>
      IS_TAURI
        ? tauriInvoke<string>('get_context').then((content) => ({ content }))
        : fetchJson('/context'),

    put: (content: string): Promise<{ ok: boolean }> =>
      IS_TAURI
        ? tauriInvoke<string>('put_context', { content }).then(() => ({ ok: true }))
        : putJson('/context', { content }),
  },

  chat: (date: string): Promise<ChatData> =>
    IS_TAURI
      ? tauriInvoke('get_chat', { date })
      : fetchJson(`/chat?date=${date}`),

  status: (): Promise<{ running: boolean; camera: boolean; mic: boolean }> =>
    IS_TAURI
      ? tauriInvoke('get_status')
      : fetchJson('/status'),

  search: (q: string, from?: string, to?: string): Promise<SearchResults> => {
    if (IS_TAURI) {
      return tauriInvoke('search_text', {
        q,
        from: from ?? null,
        to: to ?? null,
      });
    }
    const params = new URLSearchParams({ q });
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    return fetchJson(`/search?${params}`);
  },

  rag: {
    ask: (
      query: string,
      history?: { role: string; content: string }[],
    ): Promise<{
      response: string;
      sources: { type: string; timestamp: string; preview: string; distance: number }[];
    }> =>
      IS_TAURI
        ? tauriInvoke('ask_rag', { query, history: history ?? [] })
        : postJson('/rag/ask', { query, history }),
  },

  // --- Settings & devices (used by Settings component) ---

  settings: {
    get: (): Promise<unknown> =>
      IS_TAURI
        ? tauriInvoke('get_settings')
        : fetchJson('/settings'),

    put: (body: unknown): Promise<unknown> =>
      IS_TAURI
        ? tauriInvoke('put_settings', { body })
        : putJson('/settings', body),
  },

  devices: {
    get: (): Promise<unknown> =>
      IS_TAURI
        ? tauriInvoke('get_devices')
        : fetchJson('/devices'),
  },

  // --- Data management (used by DataModal) ---

  data: {
    stats: (): Promise<unknown> =>
      IS_TAURI
        ? tauriInvoke('get_data_stats')
        : fetchJson('/data/stats'),

    exportTable: (table: string, format: string = 'csv'): Promise<string> =>
      IS_TAURI
        ? tauriInvoke('export_table', { table, format })
        : fetchText(`/data/export/${table}?format=${format}`),
  },
};
