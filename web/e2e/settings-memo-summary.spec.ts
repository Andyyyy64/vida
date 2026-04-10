import { test, expect } from './fixtures';
import { makeDayStats, makeFrame, ts } from './helpers';

const DATE = '2026-04-10';

const fullSettings = {
  llm: { provider: 'gemini', gemini_model: 'gemini-3.1-flash-lite-preview', claude_model: 'haiku' },
  capture: { device: 0, interval_sec: 30, audio_device: '' },
  presence: { enabled: true, sleep_start_hour: 23, sleep_end_hour: 8 },
  chat: { enabled: false, discord_enabled: false, discord_poll_interval: 60, discord_backfill_months: 3 },
  env: {},
  env_masked: { GEMINI_API_KEY: '***' },
};

test('SummaryPanel renders scales and expanding shows items', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
      summaries: {
        [DATE]: [
          { id: 1, timestamp: ts(DATE, 9, 30), scale: '10m', content: 'ten min summary', frame_count: 20 },
          { id: 2, timestamp: ts(DATE, 10, 0), scale: '1h', content: 'hour summary text', frame_count: 120 },
          { id: 3, timestamp: ts(DATE, 11, 0), scale: '1h', content: 'another hour', frame_count: 120 },
        ],
      },
    },
  });

  await page.locator('.date-chip').filter({ hasText: DATE.slice(5) }).click();

  // 10m and 1h scale headers should be visible
  await expect(page.locator('.summary-scale-header')).toHaveCount(2);

  // Click the "1h" header (which should have count 2)
  const oneHour = page.locator('.summary-scale-header').filter({ hasText: '1h' });
  await oneHour.click();
  await expect(page.locator('.summary-scale-items .summary-item')).toHaveCount(2);
  await expect(page.locator('.summary-item').first()).toContainText('hour summary text');
});

test('MemoPanel: typing persists via runtime and is captured as write', async ({ page, mount, readWrites }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
      memos: { [DATE]: { date: DATE, content: '', updated_at: null } },
    },
  });

  await page.locator('.date-chip').filter({ hasText: DATE.slice(5) }).click();

  await page.locator('.memo-textarea').fill('My daily note');
  // Debounced save — wait a bit
  await expect.poll(async () => (await readWrites()).memos.length, { timeout: 5000 }).toBeGreaterThan(0);
  const writes = await readWrites();
  expect(writes.memos[writes.memos.length - 1]).toEqual({ date: DATE, content: 'My daily note' });
});

test('Settings modal opens via gear, edits context, saves settings, closes via Escape', async ({ page, mount, readWrites }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
      settings: fullSettings,
      devices: { cameras: [{ index: 0, name: 'Cam 0' }], audio: [{ id: 'mic1', name: 'Mic 1' }] },
    },
  });

  await page.locator('.settings-gear-btn').click();
  await expect(page.locator('.settings-overlay')).toBeVisible();

  // Context textarea edit → debounced save to context
  await page.locator('.settings-context-input').fill('Updated profile content');
  await expect.poll(async () => (await readWrites()).context.length, { timeout: 5000 }).toBeGreaterThan(0);

  // Save settings
  await page.locator('.settings-save-btn').click();
  await expect.poll(async () => (await readWrites()).settings.length, { timeout: 5000 }).toBeGreaterThan(0);

  // Escape closes
  await page.keyboard.press('Escape');
  await expect(page.locator('.settings-overlay')).toBeHidden();
});

test('i18n: language toggle switches UI strings', async ({ page, mount }) => {
  await mount({
    lang: 'en',
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
      settings: fullSettings,
      devices: { cameras: [], audio: [] },
    },
  });

  // English default — Dashboard button text
  const dashboardBtn = page.locator('.header .dashboard-btn').first();
  const enText = (await dashboardBtn.textContent())?.trim();
  expect(enText).toBeTruthy();

  await page.locator('.settings-gear-btn').click();
  await expect(page.locator('.settings-overlay')).toBeVisible();

  // Language toggle is the first .settings-toggle
  await page.locator('.settings-toggle').first().click();
  // Close settings to check header re-renders in JA
  await page.locator('.settings-close').click();

  const jaText = (await dashboardBtn.textContent())?.trim();
  expect(jaText).toBeTruthy();
  expect(jaText).not.toBe(enText);
});
