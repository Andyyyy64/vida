import { invoke, convertFileSrc } from '@tauri-apps/api/core';
import type { Runtime } from './runtime';
import type { Frame, Report, Memo, ProviderValidationRequest, ProviderValidationResult } from './types';

let dataDir = '';

export async function createTauriRuntime(): Promise<Runtime> {
  return {
    api: {
      frames: {
        list: (date) => invoke('get_frames', { date }),
        latest: () => invoke<Frame | null>('get_latest_frame').then((f) => {
          if (!f) throw new Error('No frames');
          return f;
        }),
        get: (id) => invoke<Frame | null>('get_frame', { id }).then((f) => {
          if (!f) throw new Error('Frame not found');
          return f;
        }),
      },
      summaries: { list: (date, scale) => invoke('get_summaries', { date, scale: scale ?? null }) },
      events: { list: (date) => invoke('get_events', { date }) },
      stats: {
        get: (date) => invoke('get_stats', { date }),
        dates: () => invoke('get_dates'),
        activities: (date) => invoke('get_activities', { date }),
        range: (from, to) => invoke('get_range_stats', { from, to }),
        apps: (date) => invoke('get_apps', { date }),
      },
      sessions: (date) => invoke('get_sessions', { date }),
      reports: {
        get: (date) => invoke<Report | null>('get_report', { date }).then((r) => {
          if (!r) throw new Error('Report not found');
          return r;
        }),
        list: () => invoke('list_reports'),
      },
      activities: {
        list: () => invoke('list_activities'),
        mappings: () => invoke('get_activity_mappings'),
      },
      memos: {
        get: (date) => invoke<Memo | null>('get_memo', { date }).then((m) => m ?? { date, content: '', updated_at: null }),
        put: (date, content) => invoke('put_memo', { date, content }).then(() => ({ ok: true })),
      },
      context: {
        get: () => invoke<string>('get_context').then((content) => ({ content })),
        put: (content) => invoke('put_context', { content }).then(() => ({ ok: true })),
      },
      chat: (date) => invoke('get_chat', { date }),
      status: () => invoke('get_status'),
      search: (q, from, to) => invoke('search_text', { q, from: from ?? null, to: to ?? null }),
      rag: { ask: (query, history = []) => invoke('ask_rag', { query, history }) },
      settings: {
        get: () => invoke('get_settings'),
        put: (body) => invoke('put_settings', { body }),
        validateProvider: (body: ProviderValidationRequest) => invoke<ProviderValidationResult>('validate_provider', { body }),
      },
      devices: { get: () => invoke('get_devices') },
      data: { stats: () => invoke('get_data_stats'), exportTable: (table, format = 'csv') => invoke('export_table', { table, format }) },
    },
    mediaUrl: (relativePath) => {
      if (!relativePath || !dataDir) return '';
      return convertFileSrc(`${dataDir}/${relativePath}`.replace(/\\/g, '/'));
    },
    liveFeed: {
      streamUrl: 'http://127.0.0.1:3002/stream',
      poseUrl: 'http://127.0.0.1:3002/stream/pose',
      healthUrl: 'http://127.0.0.1:3002/health',
      isLive: true,
    },
    init: async () => {
      dataDir = await invoke<string>('get_data_dir');
    },
    isDemo: false,
  };
}
