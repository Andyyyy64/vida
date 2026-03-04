import { useState, useEffect, useCallback } from 'react';

interface SettingsData {
  llm: { provider: string; gemini_model: string; claude_model: string };
  capture: { device: number; interval_sec: number; audio_device: string };
  presence: { enabled: boolean; sleep_start_hour: number; sleep_end_hour: number };
  chat: {
    enabled: boolean;
    discord_enabled: boolean;
    discord_poll_interval: number;
    discord_backfill_months: number;
  };
  env: Record<string, string>;
  env_masked: Record<string, string>;
}

interface CameraDevice { index: number; name: string }
interface AudioDevice  { id: string; name: string }
interface DeviceList   { cameras: CameraDevice[]; audio: AudioDevice[]; error?: string }

interface Props { onClose: () => void }

export function Settings({ onClose }: Props) {
  const [data, setData]           = useState<SettingsData | null>(null);
  const [devices, setDevices]     = useState<DeviceList | null>(null);
  const [devLoading, setDevLoading] = useState(true);
  const [saving, setSaving]       = useState(false);
  const [saved, setSaved]         = useState(false);
  const [error, setError]         = useState('');
  const [envInputs, setEnvInputs] = useState<Record<string, string>>({});
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});

  // Load settings and devices in parallel
  useEffect(() => {
    Promise.all([
      fetch('/api/settings').then((r) => r.json()),
      fetch('/api/devices').then((r) => r.json()),
    ])
      .then(([s, d]: [SettingsData, DeviceList]) => {
        setData(s);
        setDevices(d);
        const init: Record<string, string> = {};
        for (const k of Object.keys(s.env_masked)) init[k] = '';
        setEnvInputs(init);
      })
      .catch(() => setError('Failed to load settings'))
      .finally(() => setDevLoading(false));
  }, []);

  const handleEsc = useCallback(
    (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); },
    [onClose],
  );
  useEffect(() => {
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [handleEsc]);

  function setLlm<K extends keyof SettingsData['llm']>(k: K, v: SettingsData['llm'][K]) {
    setData((d) => d ? { ...d, llm: { ...d.llm, [k]: v } } : d);
  }
  function setCapture<K extends keyof SettingsData['capture']>(k: K, v: SettingsData['capture'][K]) {
    setData((d) => d ? { ...d, capture: { ...d.capture, [k]: v } } : d);
  }
  function setPresence<K extends keyof SettingsData['presence']>(k: K, v: SettingsData['presence'][K]) {
    setData((d) => d ? { ...d, presence: { ...d.presence, [k]: v } } : d);
  }
  function setChat<K extends keyof SettingsData['chat']>(k: K, v: SettingsData['chat'][K]) {
    setData((d) => d ? { ...d, chat: { ...d.chat, [k]: v } } : d);
  }

  async function handleSave() {
    if (!data) return;
    setSaving(true);
    setError('');
    try {
      const env: Record<string, string> = {};
      for (const [k, v] of Object.entries(envInputs)) env[k] = v;
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, env }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { error?: string }).error ?? `HTTP ${res.status}`);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      setEnvInputs((prev) => Object.fromEntries(Object.keys(prev).map((k) => [k, ''])));
      const updated = await fetch('/api/settings').then((r) => r.json()).catch(() => null);
      if (updated) setData(updated);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const cams = devices?.cameras ?? [];
  const mics = devices?.audio ?? [];

  return (
    <div
      className="settings-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="settings-modal">
        <div className="settings-header">
          <span className="settings-title">Settings</span>
          <button className="settings-close" onClick={onClose}>✕ Close</button>
        </div>

        {!data ? (
          <div className="settings-loading">{error || 'Loading…'}</div>
        ) : (
          <div className="settings-body">

            {/* ── LLM ── */}
            <section className="settings-section">
              <h3 className="settings-section-title">LLM</h3>
              <div className="settings-field">
                <label>Provider</label>
                <select value={data.llm.provider} onChange={(e) => setLlm('provider', e.target.value)}>
                  <option value="gemini">Gemini</option>
                  <option value="claude">Claude</option>
                </select>
              </div>
              <div className="settings-field">
                <label>Gemini model</label>
                <input
                  value={data.llm.gemini_model}
                  onChange={(e) => setLlm('gemini_model', e.target.value)}
                  placeholder="gemini-3.1-flash-lite-preview"
                />
              </div>
              <div className="settings-field">
                <label>Claude model</label>
                <input
                  value={data.llm.claude_model}
                  onChange={(e) => setLlm('claude_model', e.target.value)}
                  placeholder="haiku"
                />
              </div>
            </section>

            {/* ── Capture ── */}
            <section className="settings-section">
              <h3 className="settings-section-title">Capture</h3>

              {/* Camera */}
              <div className="settings-field">
                <label>
                  Camera
                  {devLoading && <span className="settings-hint"> (detecting…)</span>}
                  {devices?.error && <span className="settings-hint"> — {devices.error}</span>}
                </label>
                {cams.length > 0 ? (
                  <select
                    value={data.capture.device}
                    onChange={(e) => setCapture('device', parseInt(e.target.value))}
                  >
                    {cams.map((c) => (
                      <option key={c.index} value={c.index}>{c.name}</option>
                    ))}
                  </select>
                ) : (
                  <div className="settings-field-row">
                    <input
                      type="number"
                      min={0}
                      value={data.capture.device}
                      onChange={(e) => setCapture('device', parseInt(e.target.value) || 0)}
                      placeholder="0"
                    />
                    <span className="settings-hint-inline">
                      {devLoading ? 'Detecting cameras…' : 'No cameras found'}
                    </span>
                  </div>
                )}
              </div>

              {/* Capture interval */}
              <div className="settings-field">
                <label>Capture interval (sec)</label>
                <input
                  type="number"
                  min={5}
                  value={data.capture.interval_sec}
                  onChange={(e) => setCapture('interval_sec', parseInt(e.target.value) || 30)}
                />
              </div>

              {/* Microphone */}
              <div className="settings-field">
                <label>
                  Microphone
                  {devLoading && <span className="settings-hint"> (detecting…)</span>}
                </label>
                {mics.length > 0 ? (
                  <select
                    value={data.capture.audio_device}
                    onChange={(e) => setCapture('audio_device', e.target.value)}
                  >
                    {mics.map((m) => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </select>
                ) : (
                  <div className="settings-field-row">
                    <input
                      value={data.capture.audio_device}
                      onChange={(e) => setCapture('audio_device', e.target.value)}
                      placeholder="auto (leave blank)"
                    />
                    <span className="settings-hint-inline">
                      {devLoading ? 'Detecting…' : 'No devices found'}
                    </span>
                  </div>
                )}
                <span className="settings-hint">
                  Linux: ALSA device (e.g. plughw:1,0) &nbsp;|&nbsp; Mac/Windows: device name
                </span>
              </div>
            </section>

            {/* ── Presence ── */}
            <section className="settings-section">
              <h3 className="settings-section-title">Presence detection</h3>
              <div className="settings-field settings-field--toggle">
                <label>Enabled</label>
                <button
                  className={`settings-toggle ${data.presence.enabled ? 'on' : ''}`}
                  onClick={() => setPresence('enabled', !data.presence.enabled)}
                >
                  {data.presence.enabled ? 'ON' : 'OFF'}
                </button>
              </div>
              <div className="settings-field">
                <label>Sleep start hour (0–23)</label>
                <input
                  type="number" min={0} max={23}
                  value={data.presence.sleep_start_hour}
                  onChange={(e) => setPresence('sleep_start_hour', parseInt(e.target.value) || 0)}
                />
              </div>
              <div className="settings-field">
                <label>Sleep end hour (0–23)</label>
                <input
                  type="number" min={0} max={23}
                  value={data.presence.sleep_end_hour}
                  onChange={(e) => setPresence('sleep_end_hour', parseInt(e.target.value) || 0)}
                />
              </div>
            </section>

            {/* ── Chat ── */}
            <section className="settings-section">
              <h3 className="settings-section-title">Chat integration</h3>
              <div className="settings-field settings-field--toggle">
                <label>Chat enabled</label>
                <button
                  className={`settings-toggle ${data.chat.enabled ? 'on' : ''}`}
                  onClick={() => setChat('enabled', !data.chat.enabled)}
                >
                  {data.chat.enabled ? 'ON' : 'OFF'}
                </button>
              </div>
              <div className="settings-field settings-field--toggle">
                <label>Discord enabled</label>
                <button
                  className={`settings-toggle ${data.chat.discord_enabled ? 'on' : ''}`}
                  onClick={() => setChat('discord_enabled', !data.chat.discord_enabled)}
                >
                  {data.chat.discord_enabled ? 'ON' : 'OFF'}
                </button>
              </div>
              <div className="settings-field">
                <label>Discord poll interval (sec)</label>
                <input
                  type="number" min={10}
                  value={data.chat.discord_poll_interval}
                  onChange={(e) => setChat('discord_poll_interval', parseInt(e.target.value) || 60)}
                />
              </div>
              <div className="settings-field">
                <label>Discord backfill months</label>
                <input
                  type="number" min={0}
                  value={data.chat.discord_backfill_months}
                  onChange={(e) => setChat('discord_backfill_months', parseInt(e.target.value) || 0)}
                />
              </div>
            </section>

            {/* ── API Keys ── */}
            <section className="settings-section">
              <h3 className="settings-section-title">
                API keys <span className="settings-hint">(stored in .env)</span>
              </h3>
              {Object.keys(data.env_masked).map((key) => {
                const masked = data.env_masked[key];
                const current = envInputs[key] ?? '';
                const visible = showSecrets[key];
                return (
                  <div className="settings-field" key={key}>
                    <label>{key}</label>
                    <div className="settings-secret-row">
                      <input
                        type={visible ? 'text' : 'password'}
                        value={current}
                        placeholder={masked || 'not set'}
                        onChange={(e) => setEnvInputs((p) => ({ ...p, [key]: e.target.value }))}
                        autoComplete="off"
                      />
                      <button
                        className="settings-eye"
                        onClick={() => setShowSecrets((p) => ({ ...p, [key]: !p[key] }))}
                        title={visible ? 'Hide' : 'Show'}
                      >
                        {visible ? '🙈' : '👁'}
                      </button>
                    </div>
                  </div>
                );
              })}
              <p className="settings-hint-block">
                Leave blank to keep the current value. New values are written to <code>.env</code>.
              </p>
            </section>

          </div>
        )}

        <div className="settings-footer">
          {error && <span className="settings-error">{error}</span>}
          {saved && <span className="settings-saved">Saved ✓</span>}
          <div className="settings-footer-actions">
            <button className="settings-cancel-btn" onClick={onClose}>Cancel</button>
            <button
              className="settings-save-btn"
              onClick={handleSave}
              disabled={saving || !data}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
