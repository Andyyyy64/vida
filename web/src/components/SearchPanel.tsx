import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api';
import type { Frame, Summary } from '../lib/types';

interface Props {
  onSelectFrame: (frame: Frame) => void;
  onDateChange: (date: string) => void;
}

export function SearchPanel({ onSelectFrame, onDateChange }: Props) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [frames, setFrames] = useState<Frame[]>([]);
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  const doSearch = useCallback(async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSearched(true);
    try {
      const results = await api.search(query.trim());
      setFrames(results.frames);
      setSummaries(results.summaries);
    } catch (e) {
      console.error('Search failed:', e);
      setFrames([]);
      setSummaries([]);
    } finally {
      setSearching(false);
    }
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      doSearch();
    }
  };

  const handleFrameClick = (frame: Frame) => {
    const date = frame.timestamp.slice(0, 10);
    onDateChange(date);
    setTimeout(() => onSelectFrame(frame), 100);
  };

  const handleSummaryClick = (summary: Summary) => {
    const date = summary.timestamp.slice(0, 10);
    onDateChange(date);
  };

  const total = frames.length + summaries.length;

  return (
    <div className="search-panel">
      <div className="search-input-row">
        <input
          type="text"
          className="search-input"
          placeholder={t('search.placeholder')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button className="search-btn" onClick={doSearch} disabled={searching} aria-label={t('search.searchButton')}>
          {searching ? '...' : (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>)}
        </button>
      </div>

      {searched && (
        <div className="search-results">
          <div className="search-results-count">
            {searching ? t('search.searching') : t('common.results_count', { count: total })}
          </div>

          {frames.map((f) => (
            <div
              key={`f-${f.id}`}
              className="search-result-item"
              onClick={() => handleFrameClick(f)}
            >
              <div className="search-result-meta">
                <span className="search-result-time">
                  {f.timestamp.slice(0, 16).replace('T', ' ')}
                </span>
                {f.activity && (
                  <span className="search-result-activity">{f.activity}</span>
                )}
              </div>
              <div className="search-result-text">
                {f.claude_description || f.transcription || t('search.noDescription')}
              </div>
            </div>
          ))}

          {summaries.map((s) => (
            <div
              key={`s-${s.id}`}
              className="search-result-item"
              onClick={() => handleSummaryClick(s)}
            >
              <div className="search-result-meta">
                <span className="search-result-time">
                  {s.timestamp.slice(0, 16).replace('T', ' ')}
                </span>
                <span className="search-result-activity">{t('summary.scaleSummary', { scale: s.scale })}</span>
              </div>
              <div className="search-result-text">{s.content}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
