import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { getRuntime } from '../lib/runtime';

export function LiveFeed() {
  const { t } = useTranslation();
  const { liveFeed, isDemo } = getRuntime();
  const [live, setLive] = useState(liveFeed.isLive);
  const [expanded, setExpanded] = useState(false);
  const [showPose, setShowPose] = useState(false);

  const handleClose = useCallback(() => setExpanded(false), []);

  // Poll /health every 3s for reliable LIVE/OFFLINE detection.
  useEffect(() => {
    if (!liveFeed.healthUrl) return;
    const check = async () => {
      try {
        const res = await fetch(liveFeed.healthUrl!, { signal: AbortSignal.timeout(2000) });
        if (!res.ok) return setLive(false);
        const data = await res.json();
        setLive(!!data.live);
      } catch {
        setLive(false);
      }
    };
    check();
    const id = setInterval(check, 3000);
    return () => clearInterval(id);
  }, [liveFeed.healthUrl]);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [expanded, handleClose]);

  const label = isDemo ? t('common.demo') : t('common.live');

  if (isDemo) {
    return (
      <>
        <div className="live-feed" onClick={() => setExpanded(true)} style={{ cursor: 'pointer' }}>
          <div className="live-indicator active">
            <span className="live-dot" />
            {label}
          </div>
          <div id="demo-live-feed-preview-slot" aria-label={label} className="live-image live-image--canvas" />
        </div>
        {expanded && (
          <div className="live-modal-overlay" onClick={handleClose}>
            <div className="live-modal" onClick={(e) => e.stopPropagation()}>
              <div className="live-modal-header">
                <div className="live-indicator active">
                  <span className="live-dot" />
                  {label}
                </div>
                <div className="live-modal-controls">
                  <button className="live-modal-close" onClick={handleClose}>
                    &times;
                  </button>
                </div>
              </div>
              <div id="demo-live-feed-modal-slot" className="live-modal-canvas" />
            </div>
          </div>
        )}
      </>
    );
  }

  const modalStreamUrl = showPose ? liveFeed.poseUrl : liveFeed.streamUrl;

  if (!live) return null;

  return (
    <>
      <div className="live-feed" onClick={() => setExpanded(true)} style={{ cursor: 'pointer' }}>
        <div className="live-indicator active">
          <span className="live-dot" />
          {label}
        </div>
        <img
          src={liveFeed.streamUrl!}
          alt={label}
          className="live-image"
        />
      </div>
      {expanded && (
        <div className="live-modal-overlay" onClick={handleClose}>
          <div className="live-modal" onClick={(e) => e.stopPropagation()}>
            <div className="live-modal-header">
              <div className={`live-indicator ${live ? 'active' : ''}`}>
                <span className={`live-dot ${live ? '' : 'offline'}`} />
                {label}
              </div>
              <div className="live-modal-controls">
                <button
                  className={`live-pose-toggle ${showPose ? 'active' : ''}`}
                  onClick={() => setShowPose(!showPose)}
                  title={t('liveFeed.togglePose')}
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="8" cy="3" r="2" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                    <line x1="8" y1="5" x2="8" y2="10" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="4" y1="7" x2="12" y2="7" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="8" y1="10" x2="5" y2="14" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="8" y1="10" x2="11" y2="14" stroke="currentColor" strokeWidth="1.5"/>
                  </svg>
                  {t('liveFeed.pose')}
                </button>
                <button className="live-modal-close" onClick={handleClose}>
                  &times;
                </button>
              </div>
            </div>
            <img
              src={modalStreamUrl!}
              alt={label}
              className="live-modal-image"
            />
          </div>
        </div>
      )}
    </>
  );
}
