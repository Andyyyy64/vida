import { Hono } from 'hono';
import { getDb } from '../db.js';

const app = new Hono();

// GET /api/search?q=keyword&from=YYYY-MM-DD&to=YYYY-MM-DD&limit=50
app.get('/', (c) => {
  const q = c.req.query('q');
  if (!q || q.trim().length === 0) return c.json({ error: 'q required' }, 400);

  const from = c.req.query('from');
  const to = c.req.query('to');
  const limit = Math.min(parseInt(c.req.query('limit') || '50'), 200);

  const db = getDb();

  // Search frames via FTS5
  const frameQuery = from && to
    ? `SELECT f.*, rank FROM frames_fts fts
       JOIN frames f ON f.id = fts.rowid
       WHERE frames_fts MATCH ?
         AND f.timestamp BETWEEN ? AND ?
       ORDER BY rank LIMIT ?`
    : `SELECT f.*, rank FROM frames_fts fts
       JOIN frames f ON f.id = fts.rowid
       WHERE frames_fts MATCH ?
       ORDER BY rank LIMIT ?`;

  const frameParams = from && to
    ? [q, `${from}T00:00:00`, `${to}T23:59:59`, limit]
    : [q, limit];

  let frames: unknown[] = [];
  try {
    frames = db.prepare(frameQuery).all(...frameParams);
  } catch {
    // FTS query syntax error — try as prefix search
    const safeQ = q.replace(/['"]/g, '') + '*';
    try {
      frames = db.prepare(frameQuery).all(
        ...(from && to ? [safeQ, `${from}T00:00:00`, `${to}T23:59:59`, limit] : [safeQ, limit])
      );
    } catch {
      // ignore
    }
  }

  // Search summaries via FTS5
  const summaryQuery = from && to
    ? `SELECT s.*, rank FROM summaries_fts sfts
       JOIN summaries s ON s.id = sfts.rowid
       WHERE summaries_fts MATCH ?
         AND s.timestamp BETWEEN ? AND ?
       ORDER BY rank LIMIT ?`
    : `SELECT s.*, rank FROM summaries_fts sfts
       JOIN summaries s ON s.id = sfts.rowid
       WHERE summaries_fts MATCH ?
       ORDER BY rank LIMIT ?`;

  const summaryParams = from && to
    ? [q, `${from}T00:00:00`, `${to}T23:59:59`, limit]
    : [q, limit];

  let summaries: unknown[] = [];
  try {
    summaries = db.prepare(summaryQuery).all(...summaryParams);
  } catch {
    const safeQ = q.replace(/['"]/g, '') + '*';
    try {
      summaries = db.prepare(summaryQuery).all(
        ...(from && to ? [safeQ, `${from}T00:00:00`, `${to}T23:59:59`, limit] : [safeQ, limit])
      );
    } catch {
      // ignore
    }
  }

  return c.json({ frames, summaries });
});

export default app;
