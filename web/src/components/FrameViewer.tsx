import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

interface Props {
  framePath: string;
  screenPath: string;
  screenExtraPaths: string;
}

type ViewTab = { label: string; path: string };

export function FrameViewer({ framePath, screenPath, screenExtraPaths }: Props) {
  const { t } = useTranslation();
  const tabs: ViewTab[] = [];

  tabs.push({ label: t('detail.camera'), path: framePath });

  if (screenPath) {
    tabs.push({ label: `${t('detail.screen')} 0:00`, path: screenPath });
  }

  if (screenExtraPaths) {
    const extras = screenExtraPaths.split(',').filter(Boolean);
    extras.forEach((p, i) => {
      const sec = (i + 1) * 10;
      tabs.push({ label: `${t('detail.screen')} 0:${String(sec).padStart(2, '0')}`, path: p });
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
