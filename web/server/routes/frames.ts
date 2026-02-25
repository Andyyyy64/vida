import { Hono } from 'hono';
import { getDb } from '../db.js';

const app = new Hono();

// GET /api/frames?date=YYYY-MM-DD
app.get('/', (c) => {
  const date = c.req.query('date');
  if (!date) return c.json({ error: 'date required' }, 400);

  const db = getDb();
  const start = `${date}T00:00:00`;
  const end = `${date}T23:59:59`;

  const frames = db
    .prepare('SELECT * FROM frames WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp')
    .all(start, end);

  return c.json(frames);
});

// GET /api/frames/latest
app.get('/latest', (c) => {
  const db = getDb();
  const frame = db.prepare('SELECT * FROM frames ORDER BY timestamp DESC LIMIT 1').get();
  return c.json(frame || null);
});

// GET /api/frames/:id
app.get('/:id', (c) => {
  const id = parseInt(c.req.param('id'));
  const db = getDb();
  const frame = db.prepare('SELECT * FROM frames WHERE id = ?').get(id);
  if (!frame) return c.json({ error: 'not found' }, 404);
  return c.json(frame);
});

export default app;
