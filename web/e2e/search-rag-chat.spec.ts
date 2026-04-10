import { test, expect } from './fixtures';
import { makeDayStats, makeFrame, ts } from './helpers';

const DATE = '2026-04-10';

test('search returns frames and summaries, clicking a frame navigates and selects', async ({ page, mount }) => {
  const hit = makeFrame(42, ts(DATE, 15, 30), {
    activity: 'ドキュメント作成',
    claude_description: 'Writing design doc',
  });
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [hit, makeFrame(43, ts(DATE, 16, 0))] },
      stats: { [DATE]: makeDayStats(DATE, 2) },
      search: {
        frames: [hit],
        summaries: [
          { id: 1, timestamp: ts(DATE, 12, 0), scale: '1h', content: 'morning summary', frame_count: 10 },
        ],
      },
    },
  });

  await page.locator('.search-input').fill('design');
  await page.locator('.search-input').press('Enter');

  await expect(page.locator('.search-results-count')).toBeVisible();
  await expect(page.locator('.search-result-item')).toHaveCount(2);
  await expect(page.locator('.search-result-text').first()).toContainText('Writing design doc');

  // Click the frame result → date switches and detail opens
  await page.locator('.search-result-item').first().click();
  await expect(page.locator('.detail-id')).toHaveText('#42');
});

test('rag chat fab opens panel, send shows assistant response with sources', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
      rag: {
        response: '**Hello** from rag',
        sources: [
          { type: 'frame', timestamp: ts(DATE, 10, 0), preview: 'preview text', distance: 0.1 },
        ],
      },
    },
  });

  await page.locator('.rag-chat-fab').click();
  await expect(page.locator('.rag-chat-panel')).toBeVisible();

  await page.locator('.rag-chat-input').fill('What did I do today?');
  await page.locator('.rag-chat-send').click();

  const assistant = page.locator('.rag-chat-msg--assistant').last();
  await expect(assistant).toBeVisible();
  await expect(assistant.locator('.rag-chat-md strong')).toHaveText('Hello');
  await expect(assistant.locator('.rag-chat-source')).toHaveCount(1);
});

test('rag chat sanitizes XSS in markdown response', async ({ page, mount }) => {
  await mount({
    state: {
      rag: {
        response: 'safe <script>window.__XSS__ = true;</script> text <img src=x onerror="window.__XSS__=true">',
        sources: [],
      },
    },
  });

  await page.locator('.rag-chat-fab').click();
  await page.locator('.rag-chat-input').fill('hi');
  await page.locator('.rag-chat-send').click();

  await expect(page.locator('.rag-chat-msg--assistant').last()).toBeVisible();

  // DOMPurify must have stripped the script/onerror so no XSS fired
  const xssTriggered = await page.evaluate(() => (window as unknown as { __XSS__?: boolean }).__XSS__ === true);
  expect(xssTriggered).toBe(false);

  // Rendered HTML should not contain a <script> tag or the onerror attribute
  const html = await page.locator('.rag-chat-md').last().innerHTML();
  expect(html.toLowerCase()).not.toContain('<script');
  expect(html.toLowerCase()).not.toContain('onerror');
});

test('chat modal opens via header button and renders channels + messages', async ({ page, mount }) => {
  await mount({
    state: {
      dates: [DATE],
      frames: { [DATE]: [] },
      stats: { [DATE]: makeDayStats(DATE, 0) },
      chat: {
        [DATE]: {
          total: 2,
          channels: [
            {
              guild_id: 'g1',
              guild_name: 'MyGuild',
              channel_id: 'c1',
              channel_name: 'general',
              messages: [
                { content: 'hello world', timestamp: ts(DATE, 9, 0) },
                { content: 'second message', timestamp: ts(DATE, 9, 5) },
              ],
            },
          ],
        },
      },
    },
  });

  // Chat button is the 2nd dashboard-btn in the header
  await page.locator('.header .dashboard-btn').nth(1).click();

  const modal = page.locator('.chat-modal');
  await expect(modal).toBeVisible();
  await expect(modal.locator('.chat-modal-ch-header')).toContainText('general');

  // Channels ≤8 are auto-expanded on open
  await expect(modal.locator('.chat-modal-msg-text')).toHaveCount(2);
  await expect(modal.locator('.chat-modal-msg-text').nth(0)).toHaveText('hello world');
  await expect(modal.locator('.chat-modal-msg-text').nth(1)).toHaveText('second message');
});
