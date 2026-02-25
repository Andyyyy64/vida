import { Hono } from 'hono';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { DATA_DIR, getDb } from '../db.js';

const LIVE_STREAM_URL = process.env.LIVE_STREAM_URL || 'http://localhost:3002/stream';

const app = new Hono();

// GET /api/live/stream - proxy MJPEG stream from Python daemon
app.get('/stream', async (c) => {
  try {
    const res = await fetch(LIVE_STREAM_URL);
    if (!res.ok || !res.body) {
      return c.json({ error: 'live stream unavailable' }, 503);
    }
    return new Response(res.body, {
      headers: {
        'Content-Type': 'multipart/x-mixed-replace; boundary=frame',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  } catch {
    return c.json({ error: 'live stream unavailable' }, 503);
  }
});

// GET /api/live/frame - single JPEG snapshot (fallback)
app.get('/frame', (c) => {
  const livePath = resolve(DATA_DIR, 'live', 'latest.jpg');
  if (existsSync(livePath)) {
    const data = readFileSync(livePath);
    return new Response(data, {
      headers: {
        'Content-Type': 'image/jpeg',
        'Cache-Control': 'no-cache',
      },
    });
  }

  const db = getDb();
  const row = db.prepare('SELECT path FROM frames ORDER BY timestamp DESC LIMIT 1').get() as
    | { path: string }
    | undefined;

  if (row) {
    const framePath = resolve(DATA_DIR, row.path);
    if (existsSync(framePath)) {
      const data = readFileSync(framePath);
      return new Response(data, {
        headers: {
          'Content-Type': 'image/jpeg',
          'Cache-Control': 'no-cache',
        },
      });
    }
  }

  return c.json({ error: 'no live frame available' }, 404);
});

export default app;
