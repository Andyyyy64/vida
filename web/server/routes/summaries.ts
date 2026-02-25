import { Hono } from 'hono';
import { getDb } from '../db.js';

const app = new Hono();

// GET /api/summaries?date=YYYY-MM-DD&scale=1h
app.get('/', (c) => {
  const date = c.req.query('date');
  if (!date) return c.json({ error: 'date required' }, 400);

  const scale = c.req.query('scale');
  const db = getDb();
  const start = `${date}T00:00:00`;
  const end = `${date}T23:59:59`;

  let summaries;
  if (scale) {
    summaries = db
      .prepare(
        'SELECT * FROM summaries WHERE timestamp BETWEEN ? AND ? AND scale = ? ORDER BY timestamp',
      )
      .all(start, end, scale);
  } else {
    summaries = db
      .prepare('SELECT * FROM summaries WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp')
      .all(start, end);
  }

  return c.json(summaries);
});

export default app;
