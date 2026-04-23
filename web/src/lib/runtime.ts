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
  ProviderValidationRequest,
  ProviderValidationResult,
} from './types';

export interface RuntimeApi {
  frames: {
    list: (date: string) => Promise<Frame[]>;
    latest: () => Promise<Frame>;
    get: (id: number) => Promise<Frame>;
  };
  summaries: { list: (date: string, scale?: string) => Promise<Summary[]> };
  events: { list: (date: string) => Promise<Event[]> };
  stats: {
    get: (date: string) => Promise<DayStats>;
    dates: () => Promise<string[]>;
    activities: (date: string) => Promise<ActivityStats>;
    range: (from: string, to: string) => Promise<RangeStats>;
    apps: (date: string) => Promise<AppStat[]>;
  };
  sessions: (date: string) => Promise<Session[]>;
  reports: { get: (date: string) => Promise<Report>; list: () => Promise<Report[]> };
  activities: { list: () => Promise<ActivityInfo[]>; mappings: () => Promise<Record<string, string>> };
  memos: { get: (date: string) => Promise<Memo>; put: (date: string, content: string) => Promise<{ ok: boolean }> };
  context: { get: () => Promise<{ content: string }>; put: (content: string) => Promise<{ ok: boolean }> };
  chat: (date: string) => Promise<ChatData>;
  status: () => Promise<{ running: boolean; camera: boolean; mic: boolean }>;
  search: (q: string, from?: string, to?: string) => Promise<SearchResults>;
  rag: {
    ask: (
      query: string,
      history?: { role: string; content: string }[],
    ) => Promise<{
      response: string;
      sources: { type: string; timestamp: string; preview: string; distance: number }[];
    }>;
  };
  settings: {
    get: () => Promise<unknown>;
    put: (body: unknown) => Promise<unknown>;
    validateProvider: (body: ProviderValidationRequest) => Promise<ProviderValidationResult>;
  };
  devices: { get: () => Promise<unknown> };
  data: { stats: () => Promise<unknown>; exportTable: (table: string, format?: string) => Promise<string> };
}

export interface LiveFeedConfig {
  streamUrl: string | null;
  poseUrl: string | null;
  healthUrl: string | null;
  isLive: boolean;
}

export interface Runtime {
  api: RuntimeApi;
  mediaUrl: (relativePath: string) => string;
  liveFeed: LiveFeedConfig;
  init: () => Promise<void>;
  isDemo: boolean;
  /** Returns virtual clock Date for demo mode. Undefined in production. */
  getVirtualTime?: () => Date;
}

let runtimeSingleton: Runtime | null = null;

export function installRuntime(runtime: Runtime): void {
  runtimeSingleton = runtime;
}

export async function initRuntime(factory = () => import('./runtime-tauri').then((m) => m.createTauriRuntime())): Promise<void> {
  if (runtimeSingleton) return;
  const runtime = await factory();
  await runtime.init();
  runtimeSingleton = runtime;
}

export function getRuntime(): Runtime {
  if (!runtimeSingleton) throw new Error('Runtime has not been initialized');
  return runtimeSingleton;
}

export function resetRuntimeForTests(): void {
  runtimeSingleton = null;
}
