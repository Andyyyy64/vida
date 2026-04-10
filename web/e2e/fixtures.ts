import { test as base, expect, type Page } from '@playwright/test';
import type { E2EState, E2EWrites } from '../src/lib/runtime-e2e';

export type { E2EState, E2EWrites };

export interface MountOptions {
  state?: Partial<E2EState>;
  path?: string;
  lang?: 'ja' | 'en';
  skipOnboarding?: boolean;
}

async function mount(page: Page, opts: MountOptions = {}) {
  // Seed default settings so the warnings banner stays quiet unless a test
  // opts in to specific warning scenarios by overriding status/settings/context.
  const defaultedState: Partial<E2EState> = {
    settings: { env_masked: { GEMINI_API_KEY: '***' } },
    context: 'Test user profile',
    status: { running: true, camera: true, mic: true },
    ...opts.state,
  };
  const lang = opts.lang ?? 'en';
  const skipOnboarding = opts.skipOnboarding ?? true;
  await page.addInitScript(
    ({ state, lang, skipOnboarding }) => {
      (window as unknown as { __E2E__: boolean }).__E2E__ = true;
      (window as unknown as { __E2E_STATE__: unknown }).__E2E_STATE__ = state;
      try {
        window.localStorage.setItem('i18nextLng', lang);
        if (skipOnboarding) window.localStorage.setItem('vida_onboarded', '1');
      } catch {
        /* ignore */
      }
      // Fake WebSocket: never really connects. Tests can drive events via
      // window.__E2E_WS__.emit({type, ...}) which fan-outs to all fake sockets.
      type FakeWs = {
        readyState: number;
        onopen: ((e: Event) => void) | null;
        onmessage: ((e: MessageEvent) => void) | null;
        onerror: ((e: Event) => void) | null;
        onclose: ((e: CloseEvent) => void) | null;
        send: (data: string) => void;
        close: () => void;
        sent: string[];
      };
      const sockets: FakeWs[] = [];
      class MockWebSocket implements Partial<FakeWs> {
        static CONNECTING = 0;
        static OPEN = 1;
        static CLOSING = 2;
        static CLOSED = 3;
        readyState = 1;
        onopen: ((e: Event) => void) | null = null;
        onmessage: ((e: MessageEvent) => void) | null = null;
        onerror: ((e: Event) => void) | null = null;
        onclose: ((e: CloseEvent) => void) | null = null;
        sent: string[] = [];
        constructor(_url: string) {
          sockets.push(this as unknown as FakeWs);
          setTimeout(() => this.onopen?.(new Event('open')), 0);
        }
        send(data: string) {
          this.sent.push(data);
        }
        close() {
          this.readyState = 3;
          this.onclose?.(new CloseEvent('close'));
        }
        addEventListener() {}
        removeEventListener() {}
      }
      (window as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
      (window as unknown as { __E2E_WS__: unknown }).__E2E_WS__ = {
        sockets,
        emit(payload: unknown) {
          const data = typeof payload === 'string' ? payload : JSON.stringify(payload);
          for (const s of sockets) {
            s.onmessage?.(new MessageEvent('message', { data }));
          }
        },
      };
    },
    { state: defaultedState, lang, skipOnboarding },
  );
  await page.goto(opts.path ?? '/');
  await page.waitForFunction(() => document.querySelector('#root')?.children.length !== 0);
}

async function readWrites(page: Page): Promise<E2EWrites> {
  return page.evaluate(
    () =>
      (window as unknown as { __E2E_WRITES__?: E2EWrites }).__E2E_WRITES__ ?? {
        frames: [],
        memos: [],
        context: [],
        settings: [],
      },
  );
}

export const test = base.extend<{
  mount: (opts?: MountOptions) => Promise<void>;
  readWrites: () => Promise<E2EWrites>;
}>({
  mount: async ({ page }, use) => {
    await use((opts) => mount(page, opts));
  },
  readWrites: async ({ page }, use) => {
    await use(() => readWrites(page));
  },
});

export { expect };
