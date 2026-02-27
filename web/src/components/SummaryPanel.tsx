import { useState } from 'react';
import type { Summary } from '../lib/types';

export interface SummaryTimeRange {
  from: string;
  to: string;
}

interface Props {
  summaries: Summary[];
  onSummaryClick: (range: SummaryTimeRange) => void;
  highlightRange: SummaryTimeRange | null;
}

const SCALE_ORDER = ['24h', '12h', '6h', '1h', '30m', '10m'];

const SCALE_SECONDS: Record<string, number> = {
  '10m': 600,
  '30m': 1800,
  '1h': 3600,
  '6h': 21600,
  '12h': 43200,
  '24h': 86400,
};

function toLocalISO(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function getSummaryRange(summary: Summary): SummaryTimeRange {
  const to = new Date(summary.timestamp);
  const durationSec = SCALE_SECONDS[summary.scale] || 600;
  const from = new Date(to.getTime() - durationSec * 1000);
  // Use local ISO format to match frame timestamps (no Z suffix)
  return { from: toLocalISO(from), to: toLocalISO(to) };
}

function rangesEqual(a: SummaryTimeRange | null, b: SummaryTimeRange): boolean {
  return a !== null && a.from === b.from && a.to === b.to;
}

export function SummaryPanel({ summaries, onSummaryClick, highlightRange }: Props) {
  const [expandedScale, setExpandedScale] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const toggleExpanded = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const byScale = new Map<string, Summary[]>();
  for (const s of summaries) {
    if (!byScale.has(s.scale)) byScale.set(s.scale, []);
    byScale.get(s.scale)!.push(s);
  }

  return (
    <div className="summary-panel">
      <div className="panel-header">サマリー</div>
      {SCALE_ORDER.map((scale) => {
        const items = byScale.get(scale) || [];
        if (items.length === 0) return null;
        const isExpanded = expandedScale === scale;

        return (
          <div key={scale} className="summary-scale">
            <button
              className="summary-scale-header"
              onClick={() => setExpandedScale(isExpanded ? null : scale)}
            >
              <span className="summary-scale-name">{scale}</span>
              <span className="summary-scale-count">{items.length}</span>
            </button>
            {isExpanded && (
              <div className="summary-scale-items">
                {items.map((s) => {
                  const range = getSummaryRange(s);
                  const isActive = rangesEqual(highlightRange, range);
                  const isContentExpanded = expandedIds.has(s.id);

                  return (
                    <div
                      key={s.id}
                      className={`summary-item${isActive ? ' summary-item--active' : ''}`}
                      onClick={() => onSummaryClick(range)}
                    >
                      <div className="summary-item-time">
                        {new Date(range.from).toLocaleTimeString('ja-JP', {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                        {' — '}
                        {new Date(range.to).toLocaleTimeString('ja-JP', {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                      <div
                        className={`summary-item-content${isContentExpanded ? ' summary-item-content--expanded' : ''}`}
                      >
                        {s.content}
                      </div>
                      <div className="summary-item-footer">
                        <span className="summary-item-meta">{s.frame_count} frames</span>
                        <button
                          className="summary-expand-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleExpanded(s.id);
                          }}
                        >
                          {isContentExpanded ? '折りたたむ' : 'もっと見る'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
      {summaries.length === 0 && <div className="panel-empty">サマリーなし</div>}
    </div>
  );
}
