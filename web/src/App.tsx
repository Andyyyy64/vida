import { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { SummaryPanel } from './components/SummaryPanel';
import { Timeline } from './components/Timeline';
import { DetailPanel } from './components/DetailPanel';
import { ActivityHeatmap } from './components/ActivityHeatmap';
import { useFrames } from './hooks/useFrames';
import { useSummaries } from './hooks/useSummaries';
import { useEvents } from './hooks/useEvents';
import { api } from './lib/api';
import type { Frame, DayStats } from './lib/types';

function formatDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export default function App() {
  const [date, setDate] = useState(formatDate(new Date()));
  const [selectedFrame, setSelectedFrame] = useState<Frame | null>(null);
  const [stats, setStats] = useState<DayStats | null>(null);
  const [availableDates, setAvailableDates] = useState<string[]>([]);

  const { frames, loading: framesLoading } = useFrames(date);
  const { summaries } = useSummaries(date);
  const { events } = useEvents(date);

  useEffect(() => {
    api.stats.dates().then(setAvailableDates).catch(console.error);
  }, []);

  useEffect(() => {
    api.stats.get(date).then(setStats).catch(console.error);
  }, [date]);

  // Reset selection when date changes
  useEffect(() => {
    setSelectedFrame(null);
  }, [date]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!selectedFrame || frames.length === 0) return;
      const idx = frames.findIndex((f) => f.id === selectedFrame.id);
      if (idx === -1) return;
      if (e.key === 'ArrowLeft' && idx > 0) {
        e.preventDefault();
        setSelectedFrame(frames[idx - 1]);
      } else if (e.key === 'ArrowRight' && idx < frames.length - 1) {
        e.preventDefault();
        setSelectedFrame(frames[idx + 1]);
      }
    },
    [selectedFrame, frames],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div className="app">
      <Header
        date={date}
        onDateChange={setDate}
        availableDates={availableDates}
        frameCount={stats?.frames ?? 0}
      />
      <div className="main-layout">
        <SummaryPanel
          summaries={summaries}
          onTimeClick={(ts) => {
            const frame = frames.find((f) => f.timestamp >= ts);
            if (frame) setSelectedFrame(frame);
          }}
        />
        <Timeline
          frames={frames}
          events={events}
          selectedFrame={selectedFrame}
          onSelectFrame={setSelectedFrame}
          loading={framesLoading}
        />
        <DetailPanel frame={selectedFrame} />
      </div>
      {stats && <ActivityHeatmap activity={stats.activity} />}
    </div>
  );
}
