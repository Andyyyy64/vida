import { useRef, useEffect } from 'react';
import type { Frame, Event } from '../lib/types';

interface Props {
  frames: Frame[];
  events: Event[];
  selectedFrame: Frame | null;
  onSelectFrame: (frame: Frame) => void;
  loading: boolean;
}

function sceneColor(scene: string): string {
  switch (scene) {
    case 'dark':
      return 'var(--scene-dark)';
    case 'bright':
      return 'var(--scene-bright)';
    default:
      return 'var(--scene-normal)';
  }
}

export function Timeline({ frames, events, selectedFrame, onSelectFrame, loading }: Props) {
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
              const size = 8 + Math.min(frame.motion_score * 200, 20);

              return (
                <div
                  key={frame.id}
                  ref={isSelected ? selectedRef : undefined}
                  className={`timeline-dot${isSelected ? ' selected' : ''}${hasEvent ? ' has-event' : ''}`}
                  style={{
                    width: size,
                    height: size,
                    backgroundColor: sceneColor(frame.scene_type),
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
