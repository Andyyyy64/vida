import { afterEach, describe, expect, test, vi } from 'vitest';
import type { Runtime } from '../lib/runtime';
import {
  getRuntime,
  initRuntime,
  installRuntime,
  resetRuntimeForTests,
} from '../lib/runtime';

function createMockRuntime(): Runtime {
  return {
    api: {
      frames: {
        list: vi.fn().mockResolvedValue([]),
        latest: vi.fn(),
        get: vi.fn(),
      },
      summaries: { list: vi.fn().mockResolvedValue([]) },
      events: { list: vi.fn().mockResolvedValue([]) },
      stats: {
        get: vi.fn(),
        dates: vi.fn().mockResolvedValue([]),
        activities: vi.fn(),
        range: vi.fn(),
        apps: vi.fn(),
      },
      sessions: vi.fn(),
      reports: { get: vi.fn(), list: vi.fn() },
      activities: { list: vi.fn(), mappings: vi.fn().mockResolvedValue({}) },
      memos: { get: vi.fn(), put: vi.fn() },
      context: { get: vi.fn(), put: vi.fn() },
      chat: vi.fn(),
      status: vi.fn(),
      search: vi.fn(),
      rag: { ask: vi.fn() },
      settings: { get: vi.fn(), put: vi.fn(), validateProvider: vi.fn() },
      devices: { get: vi.fn() },
      data: { stats: vi.fn(), exportTable: vi.fn() },
    },
    mediaUrl: vi.fn((path: string) => `/demo/${path}`),
    liveFeed: {
      streamUrl: null,
      poseUrl: null,
      healthUrl: null,
      isLive: false,
    },
    init: vi.fn().mockResolvedValue(undefined),
    isDemo: true,
  };
}

describe('runtime singleton', () => {
  afterEach(() => resetRuntimeForTests());

  test('throws before initialization', () => {
    expect(() => getRuntime()).toThrow('Runtime has not been initialized');
  });

  test('returns installed runtime after initRuntime', async () => {
    const runtime = createMockRuntime();
    await initRuntime(async () => runtime);
    expect(getRuntime()).toBe(runtime);
  });

  test('installRuntime overrides singleton in tests', () => {
    const runtime = createMockRuntime();
    installRuntime(runtime);
    expect(getRuntime().isDemo).toBe(true);
  });
});
