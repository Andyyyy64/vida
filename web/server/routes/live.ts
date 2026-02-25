import { Hono } from 'hono';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { DATA_DIR, getDb } from '../db.js';

const app = new Hono();

// GET /api/live/frame
app.get('/frame', (c) => {
  // Try live/latest.jpg first (written by daemon each tick)
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

  // Fallback: serve the most recent frame from DB
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
