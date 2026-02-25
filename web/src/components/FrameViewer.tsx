import { useState } from 'react';

interface Props {
  framePath: string;
  screenPath: string;
}

export function FrameViewer({ framePath, screenPath }: Props) {
  const [view, setView] = useState<'camera' | 'screen'>('camera');

  const hasScreen = screenPath.length > 0;

  return (
    <div className="frame-viewer">
      {hasScreen && (
        <div className="frame-tabs">
          <button
            className={`frame-tab ${view === 'camera' ? 'active' : ''}`}
            onClick={() => setView('camera')}
          >
            カメラ
          </button>
          <button
            className={`frame-tab ${view === 'screen' ? 'active' : ''}`}
            onClick={() => setView('screen')}
          >
            スクリーン
          </button>
        </div>
      )}
      <div className="frame-image-container">
        <img
          src={view === 'camera' ? `/media/${framePath}` : `/media/${screenPath}`}
          alt={view === 'camera' ? 'Camera frame' : 'Screenshot'}
          className="frame-image"
          loading="lazy"
        />
      </div>
    </div>
  );
}
