import { useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import type { Frame, Event } from '../lib/types';
import type { SummaryTimeRange } from './SummaryPanel';
import { activityColor } from '../lib/activity';
import { LOCALE_MAP } from '../i18n';

interface Props {
  frames: Frame[];
  events: Event[];
  selectedFrame: Frame | null;
  onSelectFrame: (frame: Frame) => void;
  loading: boolean;
  highlightRange?: SummaryTimeRange | null;
}

export function Timeline({ frames, events, selectedFrame, onSelectFrame, loading, highlightRange }: Props) {
  const { t, i18n } = useTranslation();
  const selectedRef = useRef<HTMLDivElement>(null);
  const locale = LOCALE_MAP[i18n.language] || LOCALE_MAP[i18n.language.split('-')[0]] || 'en-US';

  useEffect(() => {
    if (selectedRef.current) {
      selectedRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [selectedFrame]);

  if (loading) {
    return (
      <div className="timeline">
        <div className="timeline-empty">{t('common.loading')}</div>
      </div>
    );
  }

  if (frames.length === 0) {
    return (
      <div className="timeline">
        <div className="timeline-empty">{t('timeline.noFrames')}</div>
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
                  title={`${new Date(frame.timestamp).toLocaleTimeString(locale)} - ${frame.claude_description || frame.scene_type}`}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
