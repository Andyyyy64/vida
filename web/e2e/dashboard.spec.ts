import { test, expect } from './fixtures';
import { makeDayStats, makeFrame, ts } from './helpers';
import type { RangeStats, ActivityStats, AppStat } from '../src/lib/types';

const DATE = '2026-04-10';

const rangeStats: RangeStats = {
  from: '2026-04-06',
  to: DATE,
  frameDuration: 30,
  totalFrames: 100,
  totalSec: 3000,
  days: [
    {
      date: DATE,
      frameCount: 50,
      totalSec: 1500,
      activities: { コーディング: 900, 会議: 600 },
      metaCategories: { focus: 30, meeting: 20, idle: 0 },
    },
  ],
  activityTotals: { コーディング: 900, 会議: 600 },
  metaTotals: { focus: 900, meeting: 600 },
};

const activityStats: ActivityStats = {
  activities: [
    { activity: 'コーディング', frameCount: 30, durationSec: 900 },
    { activity: '会議', frameCount: 20, durationSec: 600 },
  ],
  hourly: [],
};

const apps: AppStat[] = [
  { process: 'Code.exe', titleSample: 'main.ts', durationSec: 900, switchCount: 5 },
  { process: 'chrome.exe', titleSample: 'github', durationSec: 300, switchCount: 3 },
];

test('opening dashboard shows focus score, activities and app usage', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [makeFrame(1, ts(DATE, 10, 0))] },
      stats: { [DATE]: makeDayStats(DATE, 1) },
      range: rangeStats,
      activities: { [DATE]: activityStats },
      apps: { [DATE]: apps },
    },
  });

  await page.locator('.date-chip').filter({ hasText: DATE.slice(5) }).click();
  await page.locator('.dashboard-btn').first().click();

  await expect(page.locator('.dashboard-overlay')).toBeVisible();
  await expect(page.locator('.dashboard-title')).toBeVisible();

  // Focus % = focus / (totalFrames - idle) = 900 / 1500 = 60%
  await expect(page.locator('.dashboard-card').first()).toContainText('60%');

  // Activity rows
  await expect(page.locator('.dashboard-card').nth(2)).toContainText('コーディング');
  await expect(page.locator('.dashboard-card').nth(2)).toContainText('会議');

  // App usage
  await expect(page.locator('.dashboard-card').nth(3)).toContainText('Code.exe');
  await expect(page.locator('.dashboard-card').nth(3)).toContainText('chrome.exe');
});

test('dashboard closes via close button and Escape key', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
      range: rangeStats,
      activities: { [DATE]: activityStats },
      apps: { [DATE]: [] },
    },
  });

  await page.locator('.dashboard-btn').first().click();
  await expect(page.locator('.dashboard-overlay')).toBeVisible();

  await page.locator('.dashboard-close').click();
  await expect(page.locator('.dashboard-overlay')).toBeHidden();

  // Reopen → Escape closes
  await page.locator('.dashboard-btn').first().click();
  await expect(page.locator('.dashboard-overlay')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('.dashboard-overlay')).toBeHidden();
});
