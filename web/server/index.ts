import { Hono } from 'hono';
import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { compress } from 'hono/compress';
import { cors } from 'hono/cors';
import { readFileSync, existsSync, statSync, createReadStream } from 'node:fs';
import { resolve, join } from 'node:path';
import { DATA_DIR } from './db.js';
import framesRoutes from './routes/frames.js';
import summariesRoutes from './routes/summaries.js';
import eventsRoutes from './routes/events.js';
import statsRoutes from './routes/stats.js';
import liveRoutes from './routes/live.js';
import searchRoutes from './routes/search.js';
import activitiesRoutes from './routes/activities.js';
import sessionsRoutes from './routes/sessions.js';
import reportsRoutes from './routes/reports.js';
import memosRoutes from './routes/memos.js';
import chatRoutes from './routes/chat.js';
import settingsRoutes from './routes/settings.js';
import devicesRoutes from './routes/devices.js';
import exportRoutes from './routes/export.js';
import ragRoutes from './routes/rag.js';

const app = new Hono();

// --- Middleware ---

// Response compression (gzip)
app.use('*', compress());

// CORS — allow local dev origins
app.use('*', cors({
  origin: ['http://localhost:3001', 'http://localhost:5173'],
}));

// In-memory rate limiter for API routes (100 req/min per IP)
const rateLimitMap = new Map<string, { count: number; resetAt: number }>();
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX = 100;

app.use('/api/*', async (c, next) => {
  const ip = c.req.header('x-forwarded-for') ?? c.req.header('x-real-ip') ?? 'unknown';
  const now = Date.now();
  let entry = rateLimitMap.get(ip);

  if (!entry || now >= entry.resetAt) {
    entry = { count: 0, resetAt: now + RATE_LIMIT_WINDOW_MS };
    rateLimitMap.set(ip, entry);
  }

  entry.count++;

  if (entry.count > RATE_LIMIT_MAX) {
    return c.json({ error: 'Too many requests. Limit: 100 per minute.' }, 429);
  }

  await next();
});

// Periodically clean up expired rate-limit entries (every 5 min)
setInterval(() => {
  const now = Date.now();
  for (const [ip, entry] of rateLimitMap) {
    if (now >= entry.resetAt) rateLimitMap.delete(ip);
  }
}, 300_000).unref();

// Cache headers for Vite hashed static assets
app.use('/dist/assets/*', async (c, next) => {
  await next();
  c.header('Cache-Control', 'public, max-age=31536000, immutable');
});

// --- Health checks ---

app.get('/health', (c) => c.json({ status: 'ok', uptime: process.uptime() }));
app.get('/healthz', (c) => c.json({ status: 'ok', uptime: process.uptime() }));

// API routes
app.route('/api/frames', framesRoutes);
app.route('/api/summaries', summariesRoutes);
app.route('/api/events', eventsRoutes);
app.route('/api/stats', statsRoutes);
app.route('/api/live', liveRoutes);
app.route('/api/search', searchRoutes);
app.route('/api/activities', activitiesRoutes);
app.route('/api/sessions', sessionsRoutes);
app.route('/api/reports', reportsRoutes);
app.route('/api/memos', memosRoutes);
app.route('/api/chat', chatRoutes);
app.route('/api/settings', settingsRoutes);
app.route('/api/devices', devicesRoutes);
app.route('/api/export', exportRoutes);
app.route('/api/rag', ragRoutes);

// Daemon status (read from data/status.json)
app.get('/api/status', (c) => {
  const statusPath = join(DATA_DIR, 'status.json');
  if (!existsSync(statusPath)) {
    return c.json({ running: false, camera: false, mic: false });
  }
  try {
    const data = JSON.parse(readFileSync(statusPath, 'utf-8'));
    return c.json(data);
  } catch {
    return c.json({ running: false, camera: false, mic: false });
  }
});

// Media files from data directory
app.get('/media/*', (c) => {
  const reqPath = c.req.path.replace('/media/', '');
  // Prevent directory traversal
  if (reqPath.includes('..')) {
    return c.json({ error: 'forbidden' }, 403);
  }

  const fullPath = resolve(DATA_DIR, reqPath);
  // Ensure resolved path is within DATA_DIR
  if (!fullPath.startsWith(resolve(DATA_DIR))) {
    return c.json({ error: 'forbidden' }, 403);
  }

  if (!existsSync(fullPath)) {
    return c.json({ error: 'not found' }, 404);
  }

  const ext = reqPath.split('.').pop()?.toLowerCase();
  const contentTypes: Record<string, string> = {
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    png: 'image/png',
    wav: 'audio/wav',
  };
  const contentType = contentTypes[ext || ''] || 'application/octet-stream';
  const fileSize = statSync(fullPath).size;

  // Support Range requests for audio/video seeking
  const range = c.req.header('Range');
  if (range) {
    const match = range.match(/bytes=(\d+)-(\d*)/);
    if (match) {
      const start = parseInt(match[1], 10);
      const end = match[2] ? parseInt(match[2], 10) : fileSize - 1;
      const chunkSize = end - start + 1;
      const stream = createReadStream(fullPath, { start, end });
      const readable = new ReadableStream({
        start(controller) {
          stream.on('data', (chunk: Buffer | string) => controller.enqueue(chunk));
          stream.on('end', () => controller.close());
          stream.on('error', (err) => controller.error(err));
        },
        cancel() { stream.destroy(); },
      });
      return new Response(readable, {
        status: 206,
        headers: {
          'Content-Type': contentType,
          'Content-Range': `bytes ${start}-${end}/${fileSize}`,
          'Content-Length': String(chunkSize),
          'Accept-Ranges': 'bytes',
          'Cache-Control': 'public, max-age=86400',
        },
      });
    }
  }

  const data = readFileSync(fullPath);
  return new Response(data, {
    headers: {
      'Content-Type': contentType,
      'Accept-Ranges': 'bytes',
      'Content-Length': String(fileSize),
      'Cache-Control': 'public, max-age=86400',
    },
  });
});

// Static files (built frontend) - production only
app.use('/*', serveStatic({ root: './dist' }));

const port = parseInt(process.env.PORT || '3001');
console.log(`homelife.ai server running on http://localhost:${port}`);
console.log(`Data directory: ${DATA_DIR}`);
serve({ fetch: app.fetch, port });
