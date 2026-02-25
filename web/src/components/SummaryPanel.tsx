import { useState } from 'react';
import type { Summary } from '../lib/types';

interface Props {
  summaries: Summary[];
  onTimeClick: (timestamp: string) => void;
}

const SCALE_ORDER = ['24h', '12h', '6h', '1h', '30m', '10m'];

export function SummaryPanel({ summaries, onTimeClick }: Props) {
  const [expandedScale, setExpandedScale] = useState<string | null>(null);

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
                {items.map((s) => (
                  <div key={s.id} className="summary-item" onClick={() => onTimeClick(s.timestamp)}>
                    <div className="summary-item-time">
                      {new Date(s.timestamp).toLocaleTimeString('ja-JP', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </div>
                    <div className="summary-item-content">{s.content}</div>
                    <div className="summary-item-meta">{s.frame_count} frames</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
      {summaries.length === 0 && <div className="panel-empty">サマリーなし</div>}
    </div>
  );
}
