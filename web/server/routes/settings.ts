import { Hono } from 'hono';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { parse as parseToml } from 'smol-toml';

const app = new Hono();

// Repo root is one level above web/
// In packaged mode, HOMELIFE_CONFIG_DIR points to app.getPath('userData').
// In dev mode, fall back to one level above web/ (repo root).
const CONFIG_DIR = process.env.HOMELIFE_CONFIG_DIR || resolve(process.cwd(), '..');
const TOML_PATH = resolve(CONFIG_DIR, 'life.toml');
const ENV_PATH  = resolve(CONFIG_DIR, '.env');

// ── TOML helpers ─────────────────────────────────────────────────────────────

function readToml(): Record<string, unknown> {
  if (!existsSync(TOML_PATH)) return {};
  try {
    return parseToml(readFileSync(TOML_PATH, 'utf-8')) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function tomlStr(v: unknown): string {
  if (typeof v === 'string') return `"${v.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  return String(v);
}

function buildToml(s: SettingsPayload): string {
  const lines: string[] = [];

  lines.push('[llm]');
  lines.push(`provider = ${tomlStr(s.llm.provider)}`);
  lines.push(`gemini_model = ${tomlStr(s.llm.gemini_model)}`);
  lines.push(`claude_model = ${tomlStr(s.llm.claude_model)}`);
  lines.push('');

  lines.push('[capture]');
  lines.push(`device = ${Number(s.capture.device)}`);
  lines.push(`interval_sec = ${Number(s.capture.interval_sec)}`);
  if (s.capture.audio_device !== '') {
    lines.push(`audio_device = ${tomlStr(s.capture.audio_device)}`);
  }
  lines.push('');

  lines.push('[presence]');
  lines.push(`enabled = ${s.presence.enabled ? 'true' : 'false'}`);
  lines.push(`sleep_start_hour = ${Number(s.presence.sleep_start_hour)}`);
  lines.push(`sleep_end_hour = ${Number(s.presence.sleep_end_hour)}`);
  lines.push('');

  lines.push('[chat]');
  lines.push(`enabled = ${s.chat.enabled ? 'true' : 'false'}`);
  lines.push('');

  lines.push('[chat.discord]');
  lines.push(`enabled = ${s.chat.discord_enabled ? 'true' : 'false'}`);
  lines.push(`poll_interval = ${Number(s.chat.discord_poll_interval)}`);
  lines.push(`backfill_months = ${Number(s.chat.discord_backfill_months)}`);
  lines.push('');

  return lines.join('\n');
}

// ── .env helpers ─────────────────────────────────────────────────────────────

const ENV_KEYS = ['GEMINI_API_KEY', 'DISCORD_USER_TOKEN', 'DISCORD_USER_ID', 'NOTIFY_WEBHOOK_URL'];

function readEnv(): Record<string, string> {
  const result: Record<string, string> = {};
  if (!existsSync(ENV_PATH)) return result;
  const lines = readFileSync(ENV_PATH, 'utf-8').split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim().replace(/^["']|["']$/g, '');
    result[key] = val;
  }
  return result;
}

function writeEnv(updates: Record<string, string>): void {
  // Read existing content to preserve unknown keys and comments
  const existing: string[] = existsSync(ENV_PATH)
    ? readFileSync(ENV_PATH, 'utf-8').split('\n')
    : [];

  const written = new Set<string>();
  const output: string[] = [];

  for (const line of existing) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      output.push(line);
      continue;
    }
    const eq = trimmed.indexOf('=');
    if (eq === -1) { output.push(line); continue; }
    const key = trimmed.slice(0, eq).trim();
    if (key in updates) {
      if (updates[key] !== '') {
        output.push(`${key}=${updates[key]}`);
      }
      // skip empty values (don't write blank keys)
      written.add(key);
    } else {
      output.push(line);
    }
  }

  // Append new keys not already in the file
  for (const [key, val] of Object.entries(updates)) {
    if (!written.has(key) && val !== '') {
      output.push(`${key}=${val}`);
    }
  }

  // Remove trailing blank lines, then add one
  const trimmed2 = output.join('\n').trimEnd();
  writeFileSync(ENV_PATH, trimmed2 ? trimmed2 + '\n' : '');
}

function maskSecret(val: string): string {
  if (!val) return '';
  if (val.length <= 4) return '••••';
  return '••••' + val.slice(-4);
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface SettingsPayload {
  llm: {
    provider: string;
    gemini_model: string;
    claude_model: string;
  };
  capture: {
    device: number;
    interval_sec: number;
    audio_device: string;
  };
  presence: {
    enabled: boolean;
    sleep_start_hour: number;
    sleep_end_hour: number;
  };
  chat: {
    enabled: boolean;
    discord_enabled: boolean;
    discord_poll_interval: number;
    discord_backfill_months: number;
  };
  env: Record<string, string>;
}

// ── GET /api/settings ─────────────────────────────────────────────────────────

app.get('/', (c) => {
  const toml = readToml();
  const envVars = readEnv();

  const llm = (toml.llm ?? {}) as Record<string, unknown>;
  const capture = (toml.capture ?? {}) as Record<string, unknown>;
  const presence = (toml.presence ?? {}) as Record<string, unknown>;
  const chat = (toml.chat ?? {}) as Record<string, unknown>;
  const discord = (chat.discord ?? {}) as Record<string, unknown>;

  const settings: SettingsPayload & { env_masked: Record<string, string> } = {
    llm: {
      provider: String(llm.provider ?? 'gemini'),
      gemini_model: String(llm.gemini_model ?? 'gemini-3.1-flash-lite-preview'),
      claude_model: String(llm.claude_model ?? 'haiku'),
    },
    capture: {
      device: Number(capture.device ?? 0),
      interval_sec: Number(capture.interval_sec ?? 30),
      audio_device: String(capture.audio_device ?? ''),
    },
    presence: {
      enabled: presence.enabled !== false,
      sleep_start_hour: Number(presence.sleep_start_hour ?? 23),
      sleep_end_hour: Number(presence.sleep_end_hour ?? 8),
    },
    chat: {
      enabled: chat.enabled === true,
      discord_enabled: discord.enabled === true,
      discord_poll_interval: Number(discord.poll_interval ?? 60),
      discord_backfill_months: Number(discord.backfill_months ?? 3),
    },
    env: {},
    env_masked: {},
  };

  for (const key of ENV_KEYS) {
    const val = envVars[key] ?? '';
    settings.env[key] = '';  // never send actual secrets to frontend
    settings.env_masked[key] = maskSecret(val);
  }

  return c.json(settings);
});

// ── PUT /api/settings ─────────────────────────────────────────────────────────

app.put('/', async (c) => {
  let body: Partial<SettingsPayload>;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'invalid JSON' }, 400);
  }

  // Validate inputs
  if (body.llm?.provider && !['gemini', 'claude'].includes(body.llm.provider)) {
    return c.json({ error: 'Invalid LLM provider' }, 400);
  }
  if (body.capture?.interval_sec !== undefined) {
    const sec = Number(body.capture.interval_sec);
    if (!Number.isFinite(sec) || sec < 5 || sec > 3600) {
      return c.json({ error: 'Capture interval must be 5–3600 seconds' }, 400);
    }
  }
  if (body.capture?.device !== undefined) {
    const dev = Number(body.capture.device);
    if (!Number.isFinite(dev) || dev < 0) {
      return c.json({ error: 'Camera device must be >= 0' }, 400);
    }
  }
  if (body.presence?.sleep_start_hour !== undefined) {
    const h = Number(body.presence.sleep_start_hour);
    if (!Number.isFinite(h) || h < 0 || h > 23) {
      return c.json({ error: 'Sleep start hour must be 0–23' }, 400);
    }
  }
  if (body.presence?.sleep_end_hour !== undefined) {
    const h = Number(body.presence.sleep_end_hour);
    if (!Number.isFinite(h) || h < 0 || h > 23) {
      return c.json({ error: 'Sleep end hour must be 0–23' }, 400);
    }
  }
  if (body.chat?.discord_poll_interval !== undefined) {
    const sec = Number(body.chat.discord_poll_interval);
    if (!Number.isFinite(sec) || sec < 10) {
      return c.json({ error: 'Discord poll interval must be >= 10 seconds' }, 400);
    }
  }

  // Write life.toml
  const current = readToml();
  const llm = (current.llm ?? {}) as Record<string, unknown>;
  const capture = (current.capture ?? {}) as Record<string, unknown>;
  const presence = (current.presence ?? {}) as Record<string, unknown>;
  const chat = (current.chat ?? {}) as Record<string, unknown>;
  const discord = (chat.discord ?? {}) as Record<string, unknown>;

  const merged: SettingsPayload = {
    llm: {
      provider: body.llm?.provider ?? String(llm.provider ?? 'gemini'),
      gemini_model: body.llm?.gemini_model ?? String(llm.gemini_model ?? 'gemini-3.1-flash-lite-preview'),
      claude_model: body.llm?.claude_model ?? String(llm.claude_model ?? 'haiku'),
    },
    capture: {
      device: body.capture?.device ?? Number(capture.device ?? 0),
      interval_sec: body.capture?.interval_sec ?? Number(capture.interval_sec ?? 30),
      audio_device: body.capture?.audio_device ?? String(capture.audio_device ?? ''),
    },
    presence: {
      enabled: body.presence?.enabled ?? (presence.enabled !== false),
      sleep_start_hour: body.presence?.sleep_start_hour ?? Number(presence.sleep_start_hour ?? 23),
      sleep_end_hour: body.presence?.sleep_end_hour ?? Number(presence.sleep_end_hour ?? 8),
    },
    chat: {
      enabled: body.chat?.enabled ?? (chat.enabled === true),
      discord_enabled: body.chat?.discord_enabled ?? (discord.enabled === true),
      discord_poll_interval: body.chat?.discord_poll_interval ?? Number(discord.poll_interval ?? 60),
      discord_backfill_months: body.chat?.discord_backfill_months ?? Number(discord.backfill_months ?? 3),
    },
    env: body.env ?? {},
  };

  try {
    writeFileSync(TOML_PATH, buildToml(merged));
  } catch (e) {
    return c.json({ error: `Failed to write life.toml: ${e}` }, 500);
  }

  // Write .env — only update keys that were provided and non-empty placeholder
  const envUpdates: Record<string, string> = {};
  for (const key of ENV_KEYS) {
    const val = merged.env[key];
    if (val !== undefined) {
      // Skip if still the masked placeholder (user didn't change it)
      if (val.startsWith('••••')) continue;
      envUpdates[key] = val;
    }
  }
  try {
    writeEnv(envUpdates);
  } catch (e) {
    return c.json({ error: `Failed to write .env: ${e}` }, 500);
  }

  return c.json({ ok: true });
});

export default app;
