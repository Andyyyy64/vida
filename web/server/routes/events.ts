import { Hono } from 'hono';
import { getDb } from '../db.js';

const app = new Hono();

// GET /api/events?date=YYYY-MM-DD
app.get('/', (c) => {
  const date = c.req.query('date');
  if (!date) return c.json({ error: 'date required' }, 400);

  const db = getDb();
  const start = `${date}T00:00:00`;
  const end = `${date}T23:59:59`;

  const events = db
    .prepare('SELECT * FROM events WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp')
    .all(start, end);

  return c.json(events);
});

export default app;
