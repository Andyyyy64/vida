import { test, expect } from './fixtures';
import { makeDayStats, makeFrame, ts } from './helpers';

const D1 = '2026-04-09';
const D2 = '2026-04-10';

test('date chip click switches date and loads that day frames', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [D1, D2],
      frames: {
        [D1]: [makeFrame(10, ts(D1, 9, 0), { claude_description: 'yesterday frame' })],
        [D2]: [
          makeFrame(20, ts(D2, 9, 0)),
          makeFrame(21, ts(D2, 10, 0)),
        ],
      },
      stats: {
        [D1]: makeDayStats(D1, 1),
        [D2]: makeDayStats(D2, 2),
      },
    },
  });

  // App defaults to today (virtual clock not set → real today). Force D2 via chip.
  await page.locator('.date-chip').filter({ hasText: D2.slice(5) }).click();
  await expect(page.locator('.timeline-dot')).toHaveCount(2);

  await page.locator('.date-chip').filter({ hasText: D1.slice(5) }).click();
  await expect(page.locator('.timeline-dot')).toHaveCount(1);

  await page.locator('.timeline-dot').first().click();
  await expect(page.locator('.analysis-text')).toHaveText('yesterday frame');
});

test('date picker input changes the active date', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [D1, D2],
      frames: {
        [D1]: [makeFrame(10, ts(D1, 9, 0))],
        [D2]: [makeFrame(20, ts(D2, 9, 0)), makeFrame(21, ts(D2, 10, 0))],
      },
      stats: { [D1]: makeDayStats(D1, 1), [D2]: makeDayStats(D2, 2) },
    },
  });

  await page.locator('.date-picker').fill(D1);
  await expect(page.locator('.timeline-dot')).toHaveCount(1);

  await page.locator('.date-picker').fill(D2);
  await expect(page.locator('.timeline-dot')).toHaveCount(2);
});
