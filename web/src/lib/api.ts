import type { Frame, Event, Summary, DayStats, ActivityStats, SearchResults, Session, ActivityInfo, RangeStats, Report, AppStat, Memo, ChatData } from './types';

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

export const api = {
  frames: {
    list: (date: string) => fetchJson<Frame[]>(`/frames?date=${date}`),
    latest: () => fetchJson<Frame>('/frames/latest'),
    get: (id: number) => fetchJson<Frame>(`/frames/${id}`),
  },
  summaries: {
    list: (date: string, scale?: string) =>
      fetchJson<Summary[]>(`/summaries?date=${date}${scale ? `&scale=${scale}` : ''}`),
  },
  events: {
    list: (date: string) => fetchJson<Event[]>(`/events?date=${date}`),
  },
  stats: {
    get: (date: string) => fetchJson<DayStats>(`/stats?date=${date}`),
    dates: () => fetchJson<string[]>('/stats/dates'),
    activities: (date: string) => fetchJson<ActivityStats>(`/stats/activities?date=${date}`),
    range: (from: string, to: string) => fetchJson<RangeStats>(`/stats/range?from=${from}&to=${to}`),
    apps: (date: string) => fetchJson<AppStat[]>(`/stats/apps?date=${date}`),
  },
  sessions: (date: string) => fetchJson<Session[]>(`/sessions?date=${date}`),
  reports: {
    get: (date: string) => fetchJson<Report>(`/reports?date=${date}`),
    list: () => fetchJson<Report[]>('/reports'),
  },
  activities: {
    list: () => fetchJson<ActivityInfo[]>('/activities'),
  },
  memos: {
    get: (date: string) => fetchJson<Memo>(`/memos?date=${date}`),
    put: (date: string, content: string) => putJson<{ ok: boolean }>('/memos', { date, content }),
  },
  chat: (date: string) => fetchJson<ChatData>(`/chat?date=${date}`),
  status: () => fetchJson<{ running: boolean; camera: boolean; mic: boolean }>('/status'),
  search: (q: string, from?: string, to?: string) => {
    const params = new URLSearchParams({ q });
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    return fetchJson<SearchResults>(`/search?${params}`);
  },
  rag: {
    ask: (query: string, history?: { role: string; content: string }[]) =>
      postJson<{ response: string; sources: { type: string; timestamp: string; preview: string; distance: number }[] }>(
        '/rag/ask',
        { query, history },
      ),
  },
};
