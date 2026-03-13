import { Hono } from 'hono';

const RAG_URL = process.env.RAG_URL || 'http://localhost:3003';

const app = new Hono();

// POST /api/rag/ask - proxy to Python RAG server
app.post('/ask', async (c) => {
  try {
    const body = await c.req.text();
    const res = await fetch(`${RAG_URL}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    const data = await res.json();
    return c.json(data, res.status as 200);
  } catch {
    return c.json({ error: 'RAG server unavailable' }, 503);
  }
});

export default app;
