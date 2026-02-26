import type { Frame, Event, Summary, DayStats, ActivityStats, SearchResults } from './types';

const BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE}${url}`);
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
  },
  search: (q: string, from?: string, to?: string) => {
    const params = new URLSearchParams({ q });
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    return fetchJson<SearchResults>(`/search?${params}`);
  },
};
