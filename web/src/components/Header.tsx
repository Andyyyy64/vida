import { LiveFeed } from './LiveFeed';

interface Props {
  date: string;
  onDateChange: (date: string) => void;
  availableDates: string[];
  frameCount: number;
}

export function Header({ date, onDateChange, availableDates, frameCount }: Props) {
  return (
    <header className="header">
      <div className="header-left">
        <h1 className="header-title">life.ai</h1>
        <span className="header-count">{frameCount} frames</span>
      </div>
      <div className="header-center">
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
