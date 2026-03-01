import { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { SummaryPanel } from './components/SummaryPanel';
import { SearchPanel } from './components/SearchPanel';
import { MemoPanel } from './components/MemoPanel';
import { ChatModal } from './components/ChatPanel';
import { Dashboard } from './components/Dashboard';
import { Timeline } from './components/Timeline';
import { DetailPanel } from './components/DetailPanel';
import { ActivityHeatmap } from './components/ActivityHeatmap';
import { useFrames } from './hooks/useFrames';
import { useSummaries } from './hooks/useSummaries';
import { useEvents } from './hooks/useEvents';
import { useDailyMemo } from './hooks/useDailyMemo';
import { api } from './lib/api';
import { loadActivityMappings } from './lib/activity';
import { formatDate, todayStr } from './lib/date';
import type { Frame, DayStats } from './lib/types';
import type { SummaryTimeRange } from './components/SummaryPanel';

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return isMobile;
}

export default function App() {
  const [date, setDate] = useState(formatDate(new Date()));
  const [selectedFrame, setSelectedFrame] = useState<Frame | null>(null);
  const [stats, setStats] = useState<DayStats | null>(null);
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [showDashboard, setShowDashboard] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [highlightRange, setHighlightRange] = useState<SummaryTimeRange | null>(null);
  const [mobilePanel, setMobilePanel] = useState<'timeline' | 'left' | 'detail'>('timeline');
  const [warnings, setWarnings] = useState<string[]>([]);
  const isMobile = useIsMobile();

  const { frames, loading: framesLoading } = useFrames(date);
  const { summaries } = useSummaries(date);
  const { events } = useEvents(date);
  const memo = useDailyMemo(date);

  const fetchStats = useCallback(() => {
    api.stats.get(date).then(setStats).catch(console.error);
  }, [date]);

  useEffect(() => {
    loadActivityMappings().catch(console.error);
    api.stats.dates().then(setAvailableDates).catch(console.error);
    api.status().then((s) => {
      const w: string[] = [];
      if (!s.camera) w.push('Camera not available — running without webcam capture');
      setWarnings(w);
    }).catch(() => {
      setWarnings(['Daemon is not running']);
    });
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Poll stats when viewing today
  useEffect(() => {
    const isToday = date === formatDate(new Date());
    if (!isToday) return;
    const id = setInterval(fetchStats, 30_000);
    return () => clearInterval(id);
  }, [date, fetchStats]);

  // Reset selection when date changes
  useEffect(() => {
    setSelectedFrame(null);
  }, [date]);

  const handleSelectFrame = useCallback((frame: Frame) => {
    setSelectedFrame(frame);
    if (isMobile) setMobilePanel('detail');
  }, [isMobile]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (showDashboard) {
        if (e.key === 'Escape') setShowDashboard(false);
        return;
      }
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
    [selectedFrame, frames, showDashboard, showChat],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Scroll navigation: scroll down = next frame, scroll up = previous
  const handleWheel = useCallback(
    (e: WheelEvent) => {
      if (showDashboard || showChat) return;
      if (!selectedFrame || frames.length === 0) return;
      // Ignore if scrolling inside a scrollable element
      const target = e.target as HTMLElement;
      if (target.closest('.detail-panel, .left-panel, .summary-panel')) return;
      const idx = frames.findIndex((f) => f.id === selectedFrame.id);
      if (idx === -1) return;
      e.preventDefault();
      if (e.deltaY > 0 && idx < frames.length - 1) {
        setSelectedFrame(frames[idx + 1]);
      } else if (e.deltaY < 0 && idx > 0) {
        setSelectedFrame(frames[idx - 1]);
      }
    },
    [selectedFrame, frames, showDashboard, showChat],
  );

  useEffect(() => {
    window.addEventListener('wheel', handleWheel, { passive: false });
    return () => window.removeEventListener('wheel', handleWheel);
  }, [handleWheel]);

  const showLeft = !isMobile || mobilePanel === 'left';
  const showTimeline = !isMobile || mobilePanel === 'timeline';
  const showDetail = !isMobile || mobilePanel === 'detail';

  return (
    <div className="app">
      {warnings.length > 0 && (
        <div className="warning-banner">
          {warnings.map((w, i) => <span key={i}>{w}</span>)}
        </div>
      )}
      <Header
        date={date}
        onDateChange={setDate}
        availableDates={availableDates}
        frameCount={stats?.frames ?? 0}
        onDashboardClick={() => setShowDashboard(true)}
        onChatClick={() => setShowChat(true)}
      />
      {isMobile && (
        <div className="mobile-nav">
          <button
            className={`mobile-nav-btn ${mobilePanel === 'left' ? 'active' : ''}`}
            onClick={() => setMobilePanel('left')}
          >
            Summaries
          </button>
          <button
            className={`mobile-nav-btn ${mobilePanel === 'timeline' ? 'active' : ''}`}
            onClick={() => setMobilePanel('timeline')}
          >
            Timeline
          </button>
          <button
            className={`mobile-nav-btn ${mobilePanel === 'detail' ? 'active' : ''}`}
            onClick={() => setMobilePanel('detail')}
          >
            Detail
          </button>
        </div>
      )}
      <div className="main-layout">
        {showLeft && (
          <div className={`left-panel ${isMobile ? 'left-panel--mobile' : ''}`}>
            <SearchPanel
              onSelectFrame={handleSelectFrame}
              onDateChange={setDate}
            />
            <MemoPanel
              content={memo.content}
              onChange={memo.updateContent}
              saving={memo.saving}
              readonly={memo.readonly}
            />
            <SummaryPanel
              summaries={summaries}
              highlightRange={highlightRange}
              onSummaryClick={(range) => {
                // Toggle highlight: click again to deselect
                const isSame = highlightRange?.from === range.from && highlightRange?.to === range.to;
                if (isSame) {
                  setHighlightRange(null);
                } else {
                  setHighlightRange(range);
                  // Jump to first frame in range
                  const frame = frames.find((f) => f.timestamp >= range.from && f.timestamp <= range.to);
                  if (frame) handleSelectFrame(frame);
                }
              }}
            />
          </div>
        )}
        {showTimeline && (
          <Timeline
            frames={frames}
            events={events}
            selectedFrame={selectedFrame}
            onSelectFrame={handleSelectFrame}
            loading={framesLoading}
            highlightRange={highlightRange}
          />
        )}
        {showDetail && (
          <DetailPanel frame={selectedFrame} />
        )}
      </div>
      {stats && <ActivityHeatmap activity={stats.activity} />}
      {showDashboard && <Dashboard date={date} onClose={() => setShowDashboard(false)} />}
      {showChat && <ChatModal date={date} onClose={() => setShowChat(false)} />}
    </div>
  );
}
