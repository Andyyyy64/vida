import { Hono } from 'hono';
import { getDb } from '../db.js';

const app = new Hono();

function toCsv(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return '';
  const headers = Object.keys(rows[0]);
  const escape = (v: unknown): string => {
    const s = v == null ? '' : String(v);
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s;
  };
  const lines = [
    headers.join(','),
    ...rows.map((r) => headers.map((h) => escape(r[h])).join(',')),
  ];
  return lines.join('\n');
}

// GET /api/export/frames?date=YYYY-MM-DD&format=csv|json
app.get('/frames', (c) => {
  const date = c.req.query('date');
  if (!date) return c.json({ error: 'date required' }, 400);
  const format = c.req.query('format') || 'csv';

  const db = getDb();
  const start = `${date}T00:00:00`;
  const end = `${date}T23:59:59`;
  const rows = db
    .prepare('SELECT * FROM frames WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp')
    .all(start, end) as Record<string, unknown>[];

  const filename = `frames-${date}.${format === 'json' ? 'json' : 'csv'}`;

  if (format === 'json') {
    return new Response(JSON.stringify(rows, null, 2), {
      headers: {
        'Content-Type': 'application/json',
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    });
  }

  return new Response(toCsv(rows), {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${filename}"`,
    },
  });
});

// GET /api/export/summaries?from=YYYY-MM-DD&to=YYYY-MM-DD&format=csv|json
app.get('/summaries', (c) => {
  const from = c.req.query('from');
  const to = c.req.query('to');
  if (!from || !to) return c.json({ error: 'from and to required' }, 400);
  const format = c.req.query('format') || 'csv';

  const db = getDb();
  const start = `${from}T00:00:00`;
  const end = `${to}T23:59:59`;
  const rows = db
    .prepare('SELECT * FROM summaries WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp')
    .all(start, end) as Record<string, unknown>[];

  const filename = `summaries-${from}-to-${to}.${format === 'json' ? 'json' : 'csv'}`;

  if (format === 'json') {
    return new Response(JSON.stringify(rows, null, 2), {
      headers: {
        'Content-Type': 'application/json',
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    });
  }

  return new Response(toCsv(rows), {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${filename}"`,
    },
  });
});

// GET /api/export/report?date=YYYY-MM-DD
app.get('/report', (c) => {
  const date = c.req.query('date');
  if (!date) return c.json({ error: 'date required' }, 400);

  const db = getDb();
  const row = db
    .prepare('SELECT * FROM reports WHERE date = ?')
    .get(date) as Record<string, unknown> | undefined;

  if (!row) return c.json({ error: 'not found' }, 404);

  const filename = `report-${date}.json`;
  return new Response(JSON.stringify(row, null, 2), {
    headers: {
      'Content-Type': 'application/json',
      'Content-Disposition': `attachment; filename="${filename}"`,
    },
  });
});

export default app;
