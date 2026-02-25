interface Props {
  activity: number[];
}

export function ActivityHeatmap({ activity }: Props) {
  const max = Math.max(...activity, 1);

  return (
    <div className="heatmap">
      <div className="heatmap-label">活動</div>
      <div className="heatmap-grid">
        {activity.map((count, hour) => {
          const intensity = count / max;
          return (
            <div
              key={hour}
              className="heatmap-cell"
              style={{
                backgroundColor:
                  count > 0
                    ? `rgba(224, 112, 64, ${0.15 + intensity * 0.85})`
                    : 'var(--bg-surface)',
              }}
              title={`${String(hour).padStart(2, '0')}:00 - ${count} frames`}
            >
              <span className="heatmap-hour">{hour}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
