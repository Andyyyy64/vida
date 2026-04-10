import { test, expect } from './fixtures';
import { makeDayStats, makeFrame, ts } from './helpers';

const DATE = '2026-04-10';

function seedFrames() {
  return [
    makeFrame(1, ts(DATE, 9, 0), { activity: 'コーディング' }),
    makeFrame(2, ts(DATE, 10, 30), { activity: '会議', claude_description: 'In a meeting' }),
    makeFrame(3, ts(DATE, 14, 15), { activity: '休憩', claude_description: 'Taking a break' }),
  ];
}

test('renders frames as timeline dots and default empty detail', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: seedFrames() },
      stats: { [DATE]: makeDayStats(DATE, 3) },
    },
  });

  await expect(page.locator('.timeline')).toBeVisible();
  await expect(page.locator('.timeline-dot')).toHaveCount(3);
  // No frame selected yet
  await expect(page.locator('.detail-panel .panel-empty')).toBeVisible();
});

test('clicking a timeline dot opens DetailPanel with matching frame', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: seedFrames() },
      stats: { [DATE]: makeDayStats(DATE, 3) },
    },
  });

  await page.locator('.timeline-dot').nth(1).click();

  await expect(page.locator('.detail-id')).toHaveText('#2');
  await expect(page.locator('.analysis-text')).toHaveText('In a meeting');
  await expect(page.locator('.timeline-dot.selected')).toHaveCount(1);
});

test('ArrowRight / ArrowLeft navigate between frames', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: seedFrames() },
      stats: { [DATE]: makeDayStats(DATE, 3) },
    },
  });

  await page.locator('.timeline-dot').first().click();
  await expect(page.locator('.detail-id')).toHaveText('#1');

  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.detail-id')).toHaveText('#2');

  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.detail-id')).toHaveText('#3');

  // Right at end stays on last
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.detail-id')).toHaveText('#3');

  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('.detail-id')).toHaveText('#2');
});

test('clicking the camera image opens the fullscreen modal and closes on overlay click', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: seedFrames() },
      stats: { [DATE]: makeDayStats(DATE, 3) },
    },
  });

  await page.locator('.timeline-dot').first().click();
  await expect(page.locator('.detail-image-wrap')).toBeVisible();

  await page.locator('.detail-image-wrap').click();
  await expect(page.locator('.img-modal-overlay')).toBeVisible();

  await page.locator('.img-modal-overlay').click({ position: { x: 5, y: 5 } });
  await expect(page.locator('.img-modal-overlay')).toBeHidden();
});
