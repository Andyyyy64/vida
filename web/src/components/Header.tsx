import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { LiveFeed } from './LiveFeed';
import { getRuntime } from '../lib/runtime';
import { LOCALE_MAP } from '../i18n';

interface Props {
  date: string;
  onDateChange: (date: string) => void;
  availableDates: string[];
  frameCount: number;
  onDashboardClick: () => void;
  onChatClick: () => void;
  onDataClick: () => void;
  theme: 'light' | 'dark';
  onThemeToggle: () => void;
}

const DEMO_CLOCK_INTERVAL_MS = 33;
const DEFAULT_CLOCK_INTERVAL_MS = 1000;

function useClock() {
  const runtime = getRuntime();
  const [now, setNow] = useState(() => runtime.getVirtualTime?.() ?? new Date());

  useEffect(() => {
    const intervalMs = runtime.getVirtualTime ? DEMO_CLOCK_INTERVAL_MS : DEFAULT_CLOCK_INTERVAL_MS;
    const id = setInterval(() => setNow(runtime.getVirtualTime?.() ?? new Date()), intervalMs);
    return () => clearInterval(id);
  }, [runtime]);

  return now;
}

export function Header({ date, onDateChange, availableDates, frameCount, onDashboardClick, onChatClick, onDataClick, theme, onThemeToggle }: Props) {
  const { t, i18n } = useTranslation();
  const now = useClock();
  const locale = LOCALE_MAP[i18n.language] || LOCALE_MAP[i18n.language.split('-')[0]] || 'en-US';

  return (
    <header className="header">
      <div className="header-left">
        <img src="/favicon.ico" alt="vida" className="header-logo" onClick={() => window.location.reload()} />
        <span className="header-count">{t('common.frames_count', { count: frameCount })}</span>
        <button className="dashboard-btn" onClick={onDashboardClick}>
          {t('header.dashboard')}
        </button>
        <button className="dashboard-btn" onClick={onChatClick}>
          {t('header.chat')}
        </button>
        <button className="dashboard-btn" onClick={onDataClick}>
          {t('header.data')}
        </button>
      </div>
      <div className="header-center">
        <span className="header-clock">{now.toLocaleTimeString(locale)}</span>
        <input
          type="date"
          value={date}
          onChange={(e) => onDateChange(e.target.value)}
          className="date-picker"
        />
        {availableDates.length > 0 && (
          <div className="date-nav">
            {availableDates.slice(0, 7).map((d) => (
              <button
                key={d}
                className={`date-chip ${d === date ? 'active' : ''}`}
                onClick={() => onDateChange(d)}
              >
                {d.slice(5)}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="header-right">
        <button className="theme-toggle-btn" onClick={onThemeToggle} title={theme === 'dark' ? t('header.theme_light') : t('header.theme_dark')}>
          {theme === 'dark' ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>
        <LiveFeed />
      </div>
    </header>
  );
}
