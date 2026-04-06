import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api';

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
  const { t, i18n } = useTranslation();
  const [data, setData]           = useState<SettingsData | null>(null);
  const [devices, setDevices]     = useState<DeviceList | null>(null);
  const [devLoading, setDevLoading] = useState(true);
  const [saving, setSaving]       = useState(false);
  const [saved, setSaved]         = useState(false);
  const [error, setError]         = useState('');
  const [envInputs, setEnvInputs] = useState<Record<string, string>>({});
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [context, setContext] = useState('');
  const [contextSaving, setContextSaving] = useState(false);
  const contextTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load settings, devices, and context in parallel
  useEffect(() => {
    Promise.all([
      api.settings.get() as Promise<SettingsData>,
      api.devices.get() as Promise<DeviceList>,
      api.context.get().catch(() => ({ content: '' })),
    ])
      .then(([s, d, ctx]: [SettingsData, DeviceList, { content: string }]) => {
        setData(s);
        setDevices(d);
        setContext(ctx.content);
        const init: Record<string, string> = {};
        for (const k of Object.keys(s.env_masked)) init[k] = '';
        setEnvInputs(init);
      })
      .catch(() => setError(t('settings.failedToLoad')))
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
      await api.settings.put({ ...data, env });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      setEnvInputs((prev) => Object.fromEntries(Object.keys(prev).map((k) => [k, ''])));
      const updated = await api.settings.get().catch(() => null) as SettingsData | null;
      if (updated) setData(updated);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const handleContextChange = useCallback((value: string) => {
    setContext(value);
    if (contextTimer.current) clearTimeout(contextTimer.current);
    contextTimer.current = setTimeout(async () => {
      setContextSaving(true);
      try { await api.context.put(value); } catch { /* silent */ }
      setContextSaving(false);
    }, 1000);
  }, []);

  const cams = devices?.cameras ?? [];
  const mics = devices?.audio ?? [];

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === 'ja' ? 'en' : 'ja');
  };

  return (
    <div
      className="settings-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t('settings.title')}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="settings-modal">
        <div className="settings-header">
          <span className="settings-title">{t('settings.title')}</span>
          <button className="settings-close" onClick={onClose}>{t('settings.closeButton')}</button>
        </div>

        {!data ? (
          <div className="settings-loading">{error || t('common.loading')}</div>
        ) : (
          <div className="settings-body">

            {/* ── Profile (context.md) ── */}
            <section className="settings-section">
              <h3 className="settings-section-title">
                {t('settings.profile.title')}
                {contextSaving && <span className="settings-hint"> ({t('common.saving')})</span>}
              </h3>
              <p className="settings-hint-block">{t('settings.profile.description')}</p>
              <textarea
                className="settings-context-input"
                value={context}
                onChange={(e) => handleContextChange(e.target.value)}
                rows={10}
                spellCheck={false}
              />
            </section>

            {/* ── Language ── */}
            <section className="settings-section">
              <div className="settings-field settings-field--toggle">
                <label>Language / 言語</label>
                <button className="settings-toggle on" onClick={toggleLang}>
                  {i18n.language === 'ja' ? '日本語' : 'English'}
                </button>
              </div>
            </section>

            {/* ── LLM ── */}
            <section className="settings-section">
              <h3 className="settings-section-title">{t('settings.llm.title')}</h3>
              <div className="settings-field">
                <label>{t('settings.llm.provider')}</label>
                <select value={data.llm.provider} onChange={(e) => setLlm('provider', e.target.value)}>
                  <option value="gemini">Gemini</option>
                  <option value="claude">Claude</option>
                </select>
              </div>
              <div className="settings-field">
                <label>{t('settings.llm.geminiModel')}</label>
                <input
                  value={data.llm.gemini_model}
                  onChange={(e) => setLlm('gemini_model', e.target.value)}
                  placeholder="gemini-3.1-flash-lite-preview"
                />
              </div>
              <div className="settings-field">
                <label>{t('settings.llm.claudeModel')}</label>
                <input
                  value={data.llm.claude_model}
                  onChange={(e) => setLlm('claude_model', e.target.value)}
                  placeholder="haiku"
                />
              </div>
            </section>

            {/* ── Capture ── */}
            <section className="settings-section">
              <h3 className="settings-section-title">{t('settings.capture.title')}</h3>

              {/* Camera */}
              <div className="settings-field">
                <label>
                  {t('settings.capture.camera')}
                  {devLoading && <span className="settings-hint"> ({t('settings.capture.detecting')})</span>}
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
                      {devLoading ? t('settings.capture.detectingCameras') : t('settings.capture.noCameras')}
                    </span>
                  </div>
                )}
              </div>

              {/* Capture interval */}
              <div className="settings-field">
                <label>{t('settings.capture.interval')}</label>
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
                  {t('settings.capture.microphone')}
                  {devLoading && <span className="settings-hint"> ({t('settings.capture.detecting')})</span>}
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
                      placeholder={t('settings.capture.autoPlaceholder')}
                    />
                    <span className="settings-hint-inline">
                      {devLoading ? t('settings.capture.detectingDevices') : t('settings.capture.noDevices')}
                    </span>
                  </div>
                )}
                <span className="settings-hint">
                  {t('settings.capture.audioHint')}
                </span>
              </div>
            </section>

            {/* ── Presence ── */}
            <section className="settings-section">
              <h3 className="settings-section-title">{t('settings.presence.title')}</h3>
              <div className="settings-field settings-field--toggle">
                <label>{t('settings.presence.enabled')}</label>
                <button
                  className={`settings-toggle ${data.presence.enabled ? 'on' : ''}`}
                  onClick={() => setPresence('enabled', !data.presence.enabled)}
                >
                  {data.presence.enabled ? t('common.on') : t('common.off')}
                </button>
              </div>
              <div className="settings-field">
                <label>{t('settings.presence.sleepStart')}</label>
                <input
                  type="number" min={0} max={23}
                  value={data.presence.sleep_start_hour}
                  onChange={(e) => setPresence('sleep_start_hour', parseInt(e.target.value) || 0)}
                />
              </div>
              <div className="settings-field">
                <label>{t('settings.presence.sleepEnd')}</label>
                <input
                  type="number" min={0} max={23}
                  value={data.presence.sleep_end_hour}
                  onChange={(e) => setPresence('sleep_end_hour', parseInt(e.target.value) || 0)}
                />
              </div>
            </section>

            {/* ── Chat ── */}
            <section className="settings-section">
              <h3 className="settings-section-title">{t('settings.chat.title')}</h3>
              <div className="settings-field settings-field--toggle">
                <label>{t('settings.chat.enabled')}</label>
                <button
                  className={`settings-toggle ${data.chat.enabled ? 'on' : ''}`}
                  onClick={() => setChat('enabled', !data.chat.enabled)}
                >
                  {data.chat.enabled ? t('common.on') : t('common.off')}
                </button>
              </div>
              <div className="settings-field settings-field--toggle">
                <label>{t('settings.chat.discordEnabled')}</label>
                <button
                  className={`settings-toggle ${data.chat.discord_enabled ? 'on' : ''}`}
                  onClick={() => setChat('discord_enabled', !data.chat.discord_enabled)}
                >
                  {data.chat.discord_enabled ? t('common.on') : t('common.off')}
                </button>
              </div>
              <div className="settings-field">
                <label>{t('settings.chat.discordPollInterval')}</label>
                <input
                  type="number" min={10}
                  value={data.chat.discord_poll_interval}
                  onChange={(e) => setChat('discord_poll_interval', parseInt(e.target.value) || 60)}
                />
              </div>
              <div className="settings-field">
                <label>{t('settings.chat.discordBackfillMonths')}</label>
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
                {t('settings.apiKeys.title')} <span className="settings-hint">{t('settings.apiKeys.storedIn')}</span>
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
                        type={visible || !current ? 'text' : 'password'}
                        value={current}
                        placeholder={masked || t('settings.apiKeys.notSet')}
                        onChange={(e) => setEnvInputs((p) => ({ ...p, [key]: e.target.value }))}
                        autoComplete="off"
                      />
                      <button
                        className="settings-eye"
                        onClick={() => setShowSecrets((p) => ({ ...p, [key]: !p[key] }))}
                        title={visible ? t('common.hide') : t('common.show')}
                      >
                        {visible ? '🙈' : '👁'}
                      </button>
                    </div>
                  </div>
                );
              })}
              <p className="settings-hint-block" dangerouslySetInnerHTML={{ __html: t('settings.apiKeys.hint') }} />
            </section>

          </div>
        )}

        <div className="settings-footer">
          {error && <span className="settings-error">{error}</span>}
          {saved && <span className="settings-saved">{t('common.saved')}</span>}
          <div className="settings-footer-actions">
            <button className="settings-cancel-btn" onClick={onClose}>{t('common.cancel')}</button>
            <button
              className="settings-save-btn"
              onClick={handleSave}
              disabled={saving || !data}
            >
              {saving ? t('common.saving') : t('common.save')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
