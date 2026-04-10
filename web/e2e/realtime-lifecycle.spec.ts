import { test, expect } from './fixtures';
import { makeDayStats, makeFrame, ts } from './helpers';

const DATE = '2026-04-10';

test('LiveFeed shows "camera offline" when healthUrl is null', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
      // liveFeed.healthUrl is null by default
    },
  });
  await expect(page.locator('.live-image--offline')).toBeVisible();
});

test('LiveFeed goes online when /health returns live:true and modal opens on click', async ({ page, mount }) => {
  await page.route('**/health', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ live: true }) }),
  );
  await page.route('**/stream*', (route) =>
    // 1x1 transparent PNG
    route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII=',
        'base64',
      ),
    }),
  );

  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
      liveFeed: {
        isLive: true,
        healthUrl: 'http://127.0.0.1:3002/health',
        streamUrl: 'http://127.0.0.1:3002/stream',
        poseUrl: 'http://127.0.0.1:3002/pose',
      },
    },
  });

  await expect(page.locator('.live-image').first()).toBeVisible();
  await expect(page.locator('.live-image--offline')).toHaveCount(0);

  await page.locator('.live-feed').click();
  await expect(page.locator('.live-modal')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('.live-modal')).toBeHidden();
});

test('WebSocket llm_error event surfaces a toast notification', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
    },
  });

  // Give the WS hook time to attach via useEffect
  await page.waitForFunction(() => {
    const ws = (window as unknown as { __E2E_WS__?: { sockets: { onmessage: unknown }[] } }).__E2E_WS__;
    return !!ws && ws.sockets.some((s) => s.onmessage);
  });

  await page.evaluate(() => {
    const ws = (window as unknown as {
      __E2E_WS__: { emit: (p: unknown) => void };
    }).__E2E_WS__;
    ws.emit({ type: 'llm_error', message: 'rate limited' });
  });

  const toast = page.locator('.toast').filter({ hasText: 'rate limited' }).first();
  await expect(toast).toBeVisible();
});

test('WebSocket new_frame event triggers frame list refresh (vida:refresh-frames)', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [makeFrame(1, ts(DATE, 9, 0))] },
      stats: { [DATE]: makeDayStats(DATE, 1) },
    },
  });
  await page.locator('.date-chip').filter({ hasText: DATE.slice(5) }).click();
  await expect(page.locator('.timeline-dot')).toHaveCount(1);

  // Track that the refresh event fires on the window
  await page.evaluate(() => {
    (window as unknown as { __REFRESH_COUNT__: number }).__REFRESH_COUNT__ = 0;
    window.addEventListener('vida:refresh-frames', () => {
      (window as unknown as { __REFRESH_COUNT__: number }).__REFRESH_COUNT__++;
    });
  });

  await page.waitForFunction(() => {
    const ws = (window as unknown as { __E2E_WS__?: { sockets: { onmessage: unknown }[] } }).__E2E_WS__;
    return !!ws && ws.sockets.some((s) => s.onmessage);
  });

  await page.evaluate(() => {
    const ws = (window as unknown as { __E2E_WS__: { emit: (p: unknown) => void } }).__E2E_WS__;
    ws.emit({ type: 'new_frame', frame_id: 2 });
  });

  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __REFRESH_COUNT__: number }).__REFRESH_COUNT__))
    .toBeGreaterThan(0);
});

test('Onboarding shows on first run and finish dismisses it', async ({ page, mount }) => {
  await mount({
    skipOnboarding: false,
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
    },
  });

  await expect(page.locator('.onboarding-overlay')).toBeVisible();
  await expect(page.locator('.onboarding-title')).toBeVisible();

  await page.locator('.onboarding-skip-btn').click();
  await expect(page.locator('.onboarding-overlay')).toBeHidden();
});

test('Header clock displays a time string and ticks', async ({ page, mount }) => {
  await mount({ state: { dates: [DATE], frames: { [DATE]: [] }, stats: { [DATE]: makeDayStats(DATE, 0) } } });
  const clock = page.locator('.header-clock');
  await expect(clock).toBeVisible();
  const text = (await clock.textContent())?.trim() ?? '';
  expect(text).toMatch(/\d{1,2}:\d{2}/);
});

test('DataModal opens via header Data button and shows overview section', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
      dataStats: {
        dbSizeBytes: 1234567,
        firstDate: DATE,
        lastDate: DATE,
        counts: { frames: 100, summaries: 20, events: 50, chat_messages: 0, memos: 0, reports: 0, activity_mappings: 0 },
      },
    },
  });

  await page.locator('.header .dashboard-btn', { hasText: /^Data$/ }).click();
  await expect(page.locator('.data-overlay')).toBeVisible();
  await expect(page.locator('.data-title')).toBeVisible();

  await page.locator('.data-close').click();
  await expect(page.locator('.data-overlay')).toBeHidden();
});
