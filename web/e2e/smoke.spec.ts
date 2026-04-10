import { test, expect } from './fixtures';

test('app boots with fake runtime and renders header', async ({ page, mount }) => {
  const consoleErrors: string[] = [];
  page.on('pageerror', (err) => consoleErrors.push(err.message));
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await mount({
    state: {
      dates: ['2026-04-10'],
      frames: { '2026-04-10': [] },
    },
  });

  await expect(page.locator('.header')).toBeVisible();
  await expect(page.locator('.header-clock')).toBeVisible();

  expect(consoleErrors.filter((e) => !/runtime init failed/i.test(e))).toEqual([]);
});
