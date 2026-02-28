import { Hono } from 'hono';
import { getDb, getWriteDb } from '../db.js';

const app = new Hono();

// GET /api/memos?date=YYYY-MM-DD
app.get('/', (c) => {
  const date = c.req.query('date');
  if (!date) return c.json({ error: 'date required' }, 400);

  const db = getDb();
  const row = db
    .prepare('SELECT content, updated_at FROM memos WHERE date = ?')
    .get(date) as { content: string; updated_at: string } | undefined;

  return c.json({ date, content: row?.content ?? '', updated_at: row?.updated_at ?? null });
});

// PUT /api/memos — upsert memo (today only)
app.put('/', async (c) => {
  const body = await c.req.json<{ date: string; content: string }>();
  if (!body.date || typeof body.content !== 'string') {
    return c.json({ error: 'date and content required' }, 400);
  }

  // Only allow editing today's memo
  const today = new Date().toISOString().slice(0, 10);
  if (body.date !== today) {
    return c.json({ error: 'can only edit today\'s memo' }, 403);
  }

  const db = getWriteDb();
  db.prepare(
    `INSERT INTO memos (date, content, updated_at) VALUES (?, ?, datetime('now'))
     ON CONFLICT(date) DO UPDATE SET content=excluded.content, updated_at=datetime('now')`
  ).run(body.date, body.content);

  return c.json({ ok: true });
});

export default app;
