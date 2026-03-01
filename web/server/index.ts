import { Hono } from 'hono';
import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
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

const app = new Hono();

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

// Daemon status (read from data/status.json)
app.get('/api/status', (c) => {
  const statusPath = join(DATA_DIR, 'status.json');
  if (!existsSync(statusPath)) {
    return c.json({ running: false, camera: false });
  }
  try {
    const data = JSON.parse(readFileSync(statusPath, 'utf-8'));
    return c.json(data);
  } catch {
    return c.json({ running: false, camera: false });
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
          stream.on('data', (chunk: Buffer) => controller.enqueue(chunk));
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
