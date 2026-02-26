import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import type { RangeStats, Session, ActivityStats } from '../lib/types';

interface Props {
  date: string;
  onClose: () => void;
}

const META_COLORS: Record<string, string> = {
  focus: '#60a860',
  communication: '#6088d0',
  entertainment: '#d06060',
  browsing: '#d0a840',
  break: '#888888',
  other: '#a060b0',
};

const META_LABELS: Record<string, string> = {
  focus: 'Focus',
  communication: 'Communication',
  entertainment: 'Entertainment',
  browsing: 'Browsing',
  break: 'Break',
  other: 'Other',
};

function formatDuration(sec: number): string {
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm > 0 ? `${h}h${rm}m` : `${h}h`;
}

function getWeekRange(date: string): [string, string] {
  const d = new Date(date);
  const day = d.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const monday = new Date(d);
  monday.setDate(d.getDate() + mondayOffset);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return [monday.toISOString().slice(0, 10), sunday.toISOString().slice(0, 10)];
}

// Simple pie chart
function PieChart({ data }: { data: { label: string; value: number; color: string }[] }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  if (total === 0) return <div className="panel-empty">No data</div>;

  let currentAngle = -Math.PI / 2;
  const slices = data.map((d) => {
    const angle = (d.value / total) * 2 * Math.PI;
    const startAngle = currentAngle;
    currentAngle += angle;
    const endAngle = currentAngle;

    const x1 = 50 + 40 * Math.cos(startAngle);
    const y1 = 50 + 40 * Math.sin(startAngle);
    const x2 = 50 + 40 * Math.cos(endAngle);
    const y2 = 50 + 40 * Math.sin(endAngle);
    const largeArc = angle > Math.PI ? 1 : 0;

    const path =
      angle >= 2 * Math.PI - 0.001
        ? `M 50 10 A 40 40 0 1 1 49.99 10 Z`
        : `M 50 50 L ${x1} ${y1} A 40 40 0 ${largeArc} 1 ${x2} ${y2} Z`;

    return { ...d, path, pct: ((d.value / total) * 100).toFixed(0) };
  });

  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
      <svg viewBox="0 0 100 100" width="120" height="120">
        {slices.map((s, i) => (
          <path key={i} d={s.path} fill={s.color} opacity="0.85" />
        ))}
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {slices.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: s.color, flexShrink: 0 }} />
            <span style={{ color: 'var(--text-secondary)' }}>{s.label}</span>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{s.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Stacked bar chart for weekly view
function WeeklyChart({ rangeStats }: { rangeStats: RangeStats }) {
  if (rangeStats.days.length === 0) return <div className="panel-empty">No data</div>;

  const maxSec = Math.max(...rangeStats.days.map((d) => d.totalSec), 1);
  const metas = Object.keys(META_COLORS);

  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'flex-end', height: 120 }}>
      {rangeStats.days.map((day) => {
        const barHeight = (day.totalSec / maxSec) * 100;
        let currentY = 0;
        return (
          <div key={day.date} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
            <svg viewBox={`0 0 20 100`} width="100%" height={100} preserveAspectRatio="none">
              {metas.map((meta) => {
                const count = day.metaCategories[meta] || 0;
                const h = barHeight > 0 ? (count / (day.totalSec / rangeStats.frameDuration)) * barHeight : 0;
                const y = 100 - currentY - h;
                currentY += h;
                return h > 0 ? (
                  <rect key={meta} x="2" y={y} width="16" rx="1" height={h} fill={META_COLORS[meta]} opacity="0.85" />
                ) : null;
              })}
            </svg>
            <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              {day.date.slice(8)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// Session timeline (gantt-style)
function SessionTimeline({ sessions }: { sessions: Session[] }) {
  if (sessions.length === 0) return <div className="panel-empty">No sessions</div>;

  const firstTime = new Date(sessions[0].startTime).getTime();
  const lastTime = new Date(sessions[sessions.length - 1].endTime).getTime();
  const totalMs = lastTime - firstTime || 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {sessions.map((s, i) => {
        const left = ((new Date(s.startTime).getTime() - firstTime) / totalMs) * 100;
        const width = Math.max((s.durationSec * 1000 / totalMs) * 100, 1);
        return (
          <div key={i} style={{ position: 'relative', height: 20 }}>
            <div
              style={{
                position: 'absolute',
                left: `${left}%`,
                width: `${width}%`,
                height: '100%',
                background: META_COLORS[s.metaCategory] || META_COLORS.other,
                borderRadius: 3,
                opacity: 0.85,
                display: 'flex',
                alignItems: 'center',
                paddingLeft: 4,
                overflow: 'hidden',
              }}
            >
              <span style={{ fontSize: 10, whiteSpace: 'nowrap', color: '#fff' }}>
                {s.activity} ({formatDuration(s.durationSec)})
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Dashboard({ date, onClose }: Props) {
  const [rangeStats, setRangeStats] = useState<RangeStats | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [dayActivities, setDayActivities] = useState<ActivityStats | null>(null);

  useEffect(() => {
    const [weekFrom, weekTo] = getWeekRange(date);
    api.stats.range(weekFrom, weekTo).then(setRangeStats).catch(console.error);
    api.sessions(date).then(setSessions).catch(console.error);
    api.stats.activities(date).then(setDayActivities).catch(console.error);
  }, [date]);

  // Today's meta-category pie data
  const todayMeta = rangeStats?.days.find((d) => d.date === date)?.metaCategories || {};
  const pieData = Object.entries(META_COLORS).map(([meta, color]) => ({
    label: META_LABELS[meta] || meta,
    value: todayMeta[meta] || 0,
    color,
  })).filter((d) => d.value > 0);

  // Today's activity breakdown
  const activityData = (dayActivities?.activities || []).map((a, i) => ({
    label: a.activity,
    duration: formatDuration(a.durationSec),
    durationSec: a.durationSec,
    color: `hsl(${(i * 45) % 360}, 55%, 55%)`,
  }));
  const maxActivitySec = Math.max(...activityData.map((a) => a.durationSec), 1);

  // Focus time summary
  const totalFrames = rangeStats?.days.find((d) => d.date === date)?.frameCount || 0;
  const focusFrames = todayMeta['focus'] || 0;
  const focusPct = totalFrames > 0 ? Math.round((focusFrames / totalFrames) * 100) : 0;

  return (
    <div className="dashboard-overlay">
      <div className="dashboard">
        <div className="dashboard-header">
          <h2 className="dashboard-title">Dashboard</h2>
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: 13 }}>{date}</span>
          <button className="dashboard-close" onClick={onClose}>Close</button>
        </div>

        <div className="dashboard-grid">
          {/* Focus score */}
          <div className="dashboard-card">
            <div className="dashboard-card-title">Focus Score</div>
            <div style={{ fontSize: 36, fontFamily: 'var(--font-mono)', color: focusPct >= 50 ? '#60a860' : '#d0a840' }}>
              {focusPct}%
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {formatDuration((rangeStats?.days.find((d) => d.date === date)?.totalSec || 0))} tracked
            </div>
          </div>

          {/* Meta-category breakdown */}
          <div className="dashboard-card">
            <div className="dashboard-card-title">Category Breakdown</div>
            <PieChart data={pieData} />
          </div>

          {/* Activity list */}
          <div className="dashboard-card">
            <div className="dashboard-card-title">Activities</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {activityData.map((a, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                  <span style={{ minWidth: 80, color: 'var(--text-secondary)' }}>{a.label}</span>
                  <div style={{ flex: 1, height: 12, background: 'var(--bg-elevated)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ width: `${(a.durationSec / maxActivitySec) * 100}%`, height: '100%', background: a.color, borderRadius: 2 }} />
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', minWidth: 40, textAlign: 'right' }}>{a.duration}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Weekly chart */}
          <div className="dashboard-card">
            <div className="dashboard-card-title">This Week</div>
            {rangeStats && <WeeklyChart rangeStats={rangeStats} />}
            <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
              {Object.entries(META_COLORS).map(([meta, color]) => (
                <div key={meta} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                  <span style={{ color: 'var(--text-muted)' }}>{META_LABELS[meta]}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Session timeline */}
          <div className="dashboard-card" style={{ gridColumn: '1 / -1' }}>
            <div className="dashboard-card-title">Sessions</div>
            <SessionTimeline sessions={sessions} />
          </div>
        </div>
      </div>
    </div>
  );
}
