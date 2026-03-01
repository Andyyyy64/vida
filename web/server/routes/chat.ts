import { Hono } from 'hono';
import { getDb } from '../db.js';

const app = new Hono();

// GET /api/chat?date=YYYY-MM-DD
// Returns self messages grouped by guild/channel
app.get('/', (c) => {
  const date = c.req.query('date');
  if (!date) return c.json({ error: 'date required' }, 400);

  const db = getDb();
  const start = `${date}T00:00:00`;
  const end = `${date}T23:59:59`;

  const rows = db.prepare(`
    SELECT channel_id, channel_name, guild_id, guild_name,
           content, timestamp, author_name, is_self, metadata
    FROM chat_messages
    WHERE timestamp BETWEEN ? AND ? AND is_self = 1
    ORDER BY timestamp ASC
  `).all(start, end) as {
    channel_id: string;
    channel_name: string;
    guild_id: string;
    guild_name: string;
    content: string;
    timestamp: string;
    author_name: string;
    is_self: number;
    metadata: string;
  }[];

  // Group by guild → channel
  const groups: Record<string, {
    guild_id: string;
    guild_name: string;
    channel_id: string;
    channel_name: string;
    messages: { content: string; timestamp: string }[];
  }> = {};

  for (const r of rows) {
    const key = `${r.guild_id || 'dm'}:${r.channel_id}`;
    if (!groups[key]) {
      groups[key] = {
        guild_id: r.guild_id,
        guild_name: r.guild_name,
        channel_id: r.channel_id,
        channel_name: r.channel_name,
        messages: [],
      };
    }
    groups[key].messages.push({
      content: r.content,
      timestamp: r.timestamp,
    });
  }

  const channels = Object.values(groups).sort((a, b) => {
    // Sort by first message time
    return a.messages[0].timestamp.localeCompare(b.messages[0].timestamp);
  });

  return c.json({ total: rows.length, channels });
});

export default app;
