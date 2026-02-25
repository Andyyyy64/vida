import { Hono } from 'hono';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { DATA_DIR } from '../db.js';

const app = new Hono();

// GET /api/live/frame
app.get('/frame', (c) => {
  const framePath = resolve(DATA_DIR, 'live', 'latest.jpg');

  if (!existsSync(framePath)) {
    return c.json({ error: 'no live frame available' }, 404);
  }

  const data = readFileSync(framePath);
  return new Response(data, {
    headers: {
      'Content-Type': 'image/jpeg',
      'Cache-Control': 'no-cache',
    },
  });
});

export default app;
