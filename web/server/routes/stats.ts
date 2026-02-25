import { Hono } from 'hono';
import { getDb } from '../db.js';

const app = new Hono();

// GET /api/stats?date=YYYY-MM-DD
app.get('/', (c) => {
  const date = c.req.query('date');
  if (!date) return c.json({ error: 'date required' }, 400);

  const db = getDb();
  const start = `${date}T00:00:00`;
  const end = `${date}T23:59:59`;

  const frameCount = db
    .prepare('SELECT COUNT(*) as count FROM frames WHERE timestamp BETWEEN ? AND ?')
    .get(start, end) as { count: number };

  const eventCount = db
    .prepare('SELECT COUNT(*) as count FROM events WHERE timestamp BETWEEN ? AND ?')
    .get(start, end) as { count: number };

  const summaryCount = db
    .prepare('SELECT COUNT(*) as count FROM summaries WHERE timestamp BETWEEN ? AND ?')
    .get(start, end) as { count: number };

  const avgMotion = db
    .prepare('SELECT AVG(motion_score) as avg FROM frames WHERE timestamp BETWEEN ? AND ?')
    .get(start, end) as { avg: number | null };

  const avgBrightness = db
    .prepare('SELECT AVG(brightness) as avg FROM frames WHERE timestamp BETWEEN ? AND ?')
    .get(start, end) as { avg: number | null };

  // Hourly activity (frames per hour)
  const hourly = db
    .prepare(
      `SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) as count
       FROM frames WHERE timestamp BETWEEN ? AND ?
       GROUP BY hour ORDER BY hour`,
    )
    .all(start, end) as { hour: number; count: number }[];

  // Fill in all 24 hours
  const activity = Array.from({ length: 24 }, (_, i) => {
    const found = hourly.find((h) => h.hour === i);
    return found ? found.count : 0;
  });

  return c.json({
    date,
    frames: frameCount.count,
    events: eventCount.count,
    summaries: summaryCount.count,
    avgMotion: avgMotion.avg ?? 0,
    avgBrightness: avgBrightness.avg ?? 0,
    activity,
  });
});

// GET /api/stats/dates
app.get('/dates', (c) => {
  const db = getDb();
  const rows = db
    .prepare('SELECT DISTINCT date(timestamp) as d FROM frames ORDER BY d DESC')
    .all() as { d: string }[];

  return c.json(rows.map((r) => r.d));
});

export default app;
