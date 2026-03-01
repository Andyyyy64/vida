import { useState, useEffect } from 'react';
import { LiveFeed } from './LiveFeed';

interface Props {
  date: string;
  onDateChange: (date: string) => void;
  availableDates: string[];
  frameCount: number;
  onDashboardClick: () => void;
  onChatClick: () => void;
}

function useClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

export function Header({ date, onDateChange, availableDates, frameCount, onDashboardClick, onChatClick }: Props) {
  const now = useClock();

  return (
    <header className="header">
      <div className="header-left">
        <h1 className="header-title">homelife.ai</h1>
        <span className="header-count">{frameCount} frames</span>
        <button className="dashboard-btn" onClick={onChatClick}>
          Chat
        </button>
        <button className="dashboard-btn" onClick={onDashboardClick}>
          Dashboard
        </button>
      </div>
      <div className="header-center">
        <span className="header-clock">{now.toLocaleTimeString('ja-JP')}</span>
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
        <LiveFeed />
      </div>
    </header>
  );
}
