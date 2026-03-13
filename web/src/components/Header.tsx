import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { LiveFeed } from './LiveFeed';
import { LOCALE_MAP } from '../i18n';

interface Props {
  date: string;
  onDateChange: (date: string) => void;
  availableDates: string[];
  frameCount: number;
  onDashboardClick: () => void;
  onChatClick: () => void;
  theme: 'light' | 'dark';
  onThemeToggle: () => void;
}

function useClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

export function Header({ date, onDateChange, availableDates, frameCount, onDashboardClick, onChatClick, theme, onThemeToggle }: Props) {
  const { t, i18n } = useTranslation();
  const now = useClock();
  const locale = LOCALE_MAP[i18n.language] || LOCALE_MAP[i18n.language.split('-')[0]] || 'en-US';

  const handleExport = useCallback(() => {
    const url = `/api/export/frames?date=${date}&format=csv`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `frames-${date}.csv`;
    a.click();
  }, [date]);

  return (
    <header className="header">
      <div className="header-left">
        <img src="/favicon.ico" alt="homelife.ai" className="header-logo" onClick={() => window.location.reload()} />
        <span className="header-count">{t('common.frames_count', { count: frameCount })}</span>
        <button className="dashboard-btn" onClick={onChatClick}>
          {t('header.chat')}
        </button>
        <button className="dashboard-btn" onClick={onDashboardClick}>
          {t('header.dashboard')}
        </button>
        <button className="dashboard-btn" onClick={handleExport} title={t('header.export')}>
          {t('header.export')}
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
        <button className="theme-toggle-btn" onClick={onThemeToggle}>
          {theme === 'dark' ? t('header.theme_light') : t('header.theme_dark')}
        </button>
        <LiveFeed />
      </div>
    </header>
  );
}
