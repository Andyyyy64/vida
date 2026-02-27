import { useRef, useEffect } from 'react';
import type { Frame, Event } from '../lib/types';
import type { SummaryTimeRange } from './SummaryPanel';

interface Props {
  frames: Frame[];
  events: Event[];
  selectedFrame: Frame | null;
  onSelectFrame: (frame: Frame) => void;
  loading: boolean;
  highlightRange?: SummaryTimeRange | null;
}

const META_CATEGORIES: Record<string, string[]> = {
  focus: ['プログラミング', 'ドキュメント閲覧', 'コンテンツ制作', '読書'],
  communication: ['チャット', '会話'],
  entertainment: ['YouTube視聴', 'ゲーム', 'SNS', '音楽'],
  browsing: ['ブラウジング'],
  break: ['休憩', '離席', '食事'],
  idle: ['睡眠', '不在'],
};

const META_COLORS: Record<string, string> = {
  focus: '#60a860',
  communication: '#6088d0',
  entertainment: '#d06060',
  browsing: '#d0a840',
  break: '#888888',
  idle: '#444466',
  other: '#a060b0',
};

function activityColor(activity: string): string {
  if (!activity) return META_COLORS.other;
  for (const [meta, activities] of Object.entries(META_CATEGORIES)) {
    if (activities.includes(activity)) return META_COLORS[meta];
  }
  return META_COLORS.other;
}

export function Timeline({ frames, events, selectedFrame, onSelectFrame, loading, highlightRange }: Props) {
  const selectedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedRef.current) {
      selectedRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [selectedFrame]);

  if (loading) {
    return (
      <div className="timeline">
        <div className="timeline-empty">読み込み中...</div>
      </div>
    );
  }

  if (frames.length === 0) {
    return (
      <div className="timeline">
        <div className="timeline-empty">この日のフレームはありません</div>
      </div>
    );
  }

  // Group frames by hour
  const hours = new Map<number, Frame[]>();
  for (const f of frames) {
    const h = new Date(f.timestamp).getHours();
    if (!hours.has(h)) hours.set(h, []);
    hours.get(h)!.push(f);
  }

  // Event lookup by frame_id
  const eventsByFrame = new Map<number, Event[]>();
  for (const e of events) {
    if (!eventsByFrame.has(e.frame_id)) eventsByFrame.set(e.frame_id, []);
    eventsByFrame.get(e.frame_id)!.push(e);
  }

  const sortedHours = [...hours.entries()].sort((a, b) => a[0] - b[0]);

  return (
    <div className="timeline">
      {sortedHours.map(([hour, hourFrames]) => (
        <div key={hour} className="timeline-hour">
          <div className="timeline-hour-label">{String(hour).padStart(2, '0')}:00</div>
          <div className="timeline-hour-frames">
            {hourFrames.map((frame) => {
              const isSelected = selectedFrame?.id === frame.id;
              const hasEvent = eventsByFrame.has(frame.id);
              const isHighlighted = highlightRange
                ? frame.timestamp >= highlightRange.from && frame.timestamp <= highlightRange.to
                : false;
              const size = 8 + Math.min(frame.motion_score * 200, 20);

              return (
                <div
                  key={frame.id}
                  ref={isSelected ? selectedRef : undefined}
                  className={`timeline-dot${isSelected ? ' selected' : ''}${hasEvent ? ' has-event' : ''}${isHighlighted ? ' highlighted' : ''}`}
                  style={{
                    width: size,
                    height: size,
                    backgroundColor: activityColor(frame.activity),
                    opacity: highlightRange && !isHighlighted ? 0.25 : undefined,
                  }}
                  onClick={() => onSelectFrame(frame)}
                  title={`${new Date(frame.timestamp).toLocaleTimeString('ja-JP')} - ${frame.claude_description || frame.scene_type}`}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
