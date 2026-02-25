import { useState, useEffect } from 'react';

interface Props {
  framePath: string;
  screenPath: string;
  screenExtraPaths: string;
}

type ViewTab = { label: string; path: string };

export function FrameViewer({ framePath, screenPath, screenExtraPaths }: Props) {
  const tabs: ViewTab[] = [];

  tabs.push({ label: 'カメラ', path: framePath });

  if (screenPath) {
    tabs.push({ label: 'スクリーン', path: screenPath });
  }

  if (screenExtraPaths) {
    const extras = screenExtraPaths.split(',').filter(Boolean);
    extras.forEach((p, i) => {
      tabs.push({ label: `+${(i + 1) * 10}s`, path: p });
    });
  }

  const [activeIdx, setActiveIdx] = useState(0);

  // Reset tab when frame changes
  useEffect(() => {
    setActiveIdx(0);
  }, [framePath]);

  const safeIdx = activeIdx < tabs.length ? activeIdx : 0;
  const current = tabs[safeIdx];

  return (
    <div className="frame-viewer">
      {tabs.length > 1 && (
        <div className="frame-tabs">
          {tabs.map((tab, i) => (
            <button
              key={i}
              className={`frame-tab ${i === safeIdx ? 'active' : ''}`}
              onClick={() => setActiveIdx(i)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}
      <div className="frame-image-container">
        <img
          key={current.path}
          src={`/media/${current.path}`}
          alt={current.label}
          className="frame-image"
        />
      </div>
    </div>
  );
}
