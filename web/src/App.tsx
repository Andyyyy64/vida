import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Header } from './components/Header';
import { SummaryPanel } from './components/SummaryPanel';
import { SearchPanel } from './components/SearchPanel';
import { MemoPanel } from './components/MemoPanel';
import { Timeline } from './components/Timeline';
import { DetailPanel } from './components/DetailPanel';
import { ActivityHeatmap } from './components/ActivityHeatmap';
import { RagChat } from './components/RagChat';

const Dashboard = lazy(() => import('./components/Dashboard').then(m => ({ default: m.Dashboard })));
const Settings = lazy(() => import('./components/Settings').then(m => ({ default: m.Settings })));
const ChatModal = lazy(() => import('./components/ChatPanel').then(m => ({ default: m.ChatModal })));
const DataModal = lazy(() => import('./components/DataModal').then(m => ({ default: m.DataModal })));
const Onboarding = lazy(() => import('./components/Onboarding').then(m => ({ default: m.Onboarding })));
import { useFrames } from './hooks/useFrames';
import { useSummaries } from './hooks/useSummaries';
import { useEvents } from './hooks/useEvents';
import { useDailyMemo } from './hooks/useDailyMemo';
import { useToast } from './hooks/useToast';
import { api } from './lib/api';
import { loadActivityMappings } from './lib/activity';
import { formatDate } from './lib/date';
import { getLiveDataPollInterval, resolveDemoSelectedFrame } from './lib/demo-runtime';
import { getRuntime } from './lib/runtime';
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

function getInitialTheme(): 'light' | 'dark' {
  const stored = localStorage.getItem('vida_theme');
  if (stored === 'light' || stored === 'dark') return stored;
  if (window.matchMedia?.('(prefers-color-scheme: light)').matches) return 'light';
  return 'dark';
}

function getInitialDate(): string {
  const runtime = getRuntime();
  return formatDate(runtime.getVirtualTime?.() ?? new Date());
}

export default function App() {
  const { t } = useTranslation();
  const runtime = getRuntime();
  const isDemo = runtime.isDemo;
  const [theme, setTheme] = useState<'light' | 'dark'>(getInitialTheme);
  const [date, setDate] = useState(getInitialDate);
  const [selectedFrame, setSelectedFrame] = useState<Frame | null>(null);
  const [stats, setStats] = useState<DayStats | null>(null);
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [showDashboard, setShowDashboard] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [showData, setShowData] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(() => localStorage.getItem('vida_onboarded') !== '1');
  const [highlightRange, setHighlightRange] = useState<SummaryTimeRange | null>(null);
  const [mobilePanel, setMobilePanel] = useState<'timeline' | 'left' | 'detail'>('timeline');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [demoAutoFollowLatest, setDemoAutoFollowLatest] = useState(true);
  const isMobile = useIsMobile();
  const { addToast } = useToast();

  const { frames, loading: framesLoading } = useFrames(date);
  const { summaries } = useSummaries(date);
  const { events } = useEvents(date);
  const memo = useDailyMemo(date);

  const fetchStats = useCallback(() => {
    api.stats.get(date).then(setStats).catch(() => {
      addToast(t('errors.fetchStats'), 'error');
    });
  }, [date, addToast, t]);

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('vida_theme', theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  useEffect(() => {
    loadActivityMappings().catch(console.error);
    api.stats.dates().then((dates) => {
      setAvailableDates(dates);
      if (dates.length > 0 && !dates.includes(date)) {
        setDate(dates[dates.length - 1]);
      }
    }).catch(console.error);
    Promise.all([
      api.status(),
      api.settings.get() as Promise<{ env_masked: Record<string, string> }>,
      api.context.get().catch(() => ({ content: '' })),
    ]).then(([s, settings, ctx]) => {
      const w: string[] = [];
      if (!s.camera && !s.mic) {
        w.push('warnings.noCameraAndMic');
      } else {
        if (!s.camera) w.push('warnings.noCamera');
        if (!s.mic) w.push('warnings.noMic');
      }
      if (!settings.env_masked?.GEMINI_API_KEY) {
        w.push('warnings.apiKeyRequired');
      }
      if (!ctx.content?.trim()) {
        w.push('warnings.profileRecommended');
      }
      setWarnings(w);
    }).catch(() => {
      setWarnings(['warnings.daemonNotRunning']);
    });
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Poll stats when viewing today
  useEffect(() => {
    const isToday = date === formatDate(new Date());
    if (!isDemo && !isToday) return;
    const id = setInterval(fetchStats, getLiveDataPollInterval(isDemo));
    return () => clearInterval(id);
  }, [date, fetchStats, isDemo]);

  // Reset selection when date changes
  useEffect(() => {
    setSelectedFrame(null);
    setDemoAutoFollowLatest(true);
  }, [date]);

  useEffect(() => {
    const nextFrame = resolveDemoSelectedFrame({
      isDemo,
      autoFollowLatest: demoAutoFollowLatest,
      previousSelectedFrame: selectedFrame,
      frames,
    });
    if (!nextFrame) return;
    if (selectedFrame?.timestamp === nextFrame.timestamp && selectedFrame.id === nextFrame.id) return;
    setSelectedFrame(nextFrame);
  }, [demoAutoFollowLatest, frames, isDemo, selectedFrame]);

  const handleSelectFrame = useCallback((frame: Frame, options?: { autoFollowLatest?: boolean }) => {
    setSelectedFrame(frame);
    if (isDemo) {
      const isLatestFrame = frames[frames.length - 1]?.timestamp === frame.timestamp;
      setDemoAutoFollowLatest(options?.autoFollowLatest ?? isLatestFrame);
    }
    if (isMobile) setMobilePanel('detail');
  }, [frames, isDemo, isMobile]);

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
        if (isDemo) setDemoAutoFollowLatest(false);
        setSelectedFrame(frames[idx - 1]);
      } else if (e.key === 'ArrowRight' && idx < frames.length - 1) {
        e.preventDefault();
        if (isDemo) setDemoAutoFollowLatest(false);
        setSelectedFrame(frames[idx + 1]);
      }
    },
    [isDemo, selectedFrame, frames, showDashboard, showChat],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Scroll navigation: scroll down = next frame, scroll up = previous
  const handleWheel = useCallback(
    (e: WheelEvent) => {
      if (showDashboard || showChat || showSettings || showData) return;
      if (!selectedFrame || frames.length === 0) return;
      // Ignore if scrolling inside a scrollable element
      const target = e.target as HTMLElement;
      if (target.closest('.detail-panel, .left-panel, .summary-panel')) return;
      const idx = frames.findIndex((f) => f.id === selectedFrame.id);
      if (idx === -1) return;
      e.preventDefault();
      if (e.deltaY > 0 && idx < frames.length - 1) {
        if (isDemo) setDemoAutoFollowLatest(false);
        setSelectedFrame(frames[idx + 1]);
      } else if (e.deltaY < 0 && idx > 0) {
        if (isDemo) setDemoAutoFollowLatest(false);
        setSelectedFrame(frames[idx - 1]);
      }
    },
    [isDemo, selectedFrame, frames, showDashboard, showChat, showSettings, showData],
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
        <div className="warning-banner" role="alert" aria-live="polite">
          {warnings.map((w, i) => <span key={i}>{t(w)}</span>)}
        </div>
      )}
      <Header
        date={date}
        onDateChange={setDate}
        availableDates={availableDates}
        frameCount={stats?.frames ?? 0}
        onDashboardClick={() => setShowDashboard(true)}
        onChatClick={() => setShowChat(true)}
        onDataClick={() => setShowData(true)}
        theme={theme}
        onThemeToggle={toggleTheme}
      />
      {isMobile && (
        <nav className="mobile-nav" aria-label="Panel navigation">
          <button
            className={`mobile-nav-btn ${mobilePanel === 'left' ? 'active' : ''}`}
            onClick={() => setMobilePanel('left')}
          >
            {t('nav.summaries')}
          </button>
          <button
            className={`mobile-nav-btn ${mobilePanel === 'timeline' ? 'active' : ''}`}
            onClick={() => setMobilePanel('timeline')}
          >
            {t('nav.timeline')}
          </button>
          <button
            className={`mobile-nav-btn ${mobilePanel === 'detail' ? 'active' : ''}`}
            onClick={() => setMobilePanel('detail')}
          >
            {t('nav.detail')}
          </button>
        </nav>
      )}
      <main className="main-layout" role="main">
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
                  if (frame) handleSelectFrame(frame, { autoFollowLatest: false });
                }
              }}
            />
          </div>
        )}
        {showTimeline && (
          <div className="timeline-wrapper">
            <Timeline
              frames={frames}
              events={events}
              selectedFrame={selectedFrame}
              onSelectFrame={handleSelectFrame}
              loading={framesLoading}
              highlightRange={highlightRange}
            />
            <RagChat />
          </div>
        )}
        {showDetail && (
          <DetailPanel frame={selectedFrame} />
        )}
      </main>
      {stats && <ActivityHeatmap activity={stats.activity} />}
      <Suspense fallback={null}>
        {showDashboard && <Dashboard date={date} onClose={() => setShowDashboard(false)} />}
        {showChat && <ChatModal date={date} onClose={() => setShowChat(false)} />}
        {showData && <DataModal onClose={() => setShowData(false)} />}
        {showSettings && <Settings onClose={() => setShowSettings(false)} />}
        {showOnboarding && (
          <Onboarding
            onClose={() => setShowOnboarding(false)}
            onOpenSettings={() => setShowSettings(true)}
          />
        )}
      </Suspense>
      <button
        className="settings-gear-btn"
        onClick={() => setShowSettings(true)}
        title={t('settings.title')}
        aria-label={t('settings.title')}
      >
        ⚙
      </button>
      {isDemo && (
        <div className="demo-footer-banner">
          {t('demo.simulatedBanner')}
        </div>
      )}
    </div>
  );
}
