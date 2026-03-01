import { useState, useEffect, useCallback } from 'react';

const BASE_URL = `${window.location.protocol}//${window.location.hostname}:3002`;
const STREAM_URL = `${BASE_URL}/stream`;
const STREAM_POSE_URL = `${BASE_URL}/stream/pose`;

export function LiveFeed() {
  const [live, setLive] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showPose, setShowPose] = useState(false);

  const handleClose = useCallback(() => setExpanded(false), []);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [expanded, handleClose]);

  const modalStreamUrl = showPose ? STREAM_POSE_URL : STREAM_URL;

  return (
    <>
      <div className="live-feed" onClick={() => live && setExpanded(true)} style={{ cursor: live ? 'pointer' : 'default' }}>
        <div className={`live-indicator ${live ? 'active' : ''}`}>
          <span className={`live-dot ${live ? '' : 'offline'}`} />
          {live ? 'LIVE' : 'OFFLINE'}
        </div>
        <img
          src={STREAM_URL}
          alt="Live feed"
          className="live-image"
          style={{ display: live ? 'block' : 'none' }}
          onLoad={() => setLive(true)}
          onError={() => setLive(false)}
        />
      </div>
      {expanded && (
        <div className="live-modal-overlay" onClick={handleClose}>
          <div className="live-modal" onClick={(e) => e.stopPropagation()}>
            <div className="live-modal-header">
              <div className={`live-indicator ${live ? 'active' : ''}`}>
                <span className={`live-dot ${live ? '' : 'offline'}`} />
                LIVE
              </div>
              <div className="live-modal-controls">
                <button
                  className={`live-pose-toggle ${showPose ? 'active' : ''}`}
                  onClick={() => setShowPose(!showPose)}
                  title="Toggle pose skeleton overlay"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="8" cy="3" r="2" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                    <line x1="8" y1="5" x2="8" y2="10" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="4" y1="7" x2="12" y2="7" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="8" y1="10" x2="5" y2="14" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="8" y1="10" x2="11" y2="14" stroke="currentColor" strokeWidth="1.5"/>
                  </svg>
                  Pose
                </button>
                <button className="live-modal-close" onClick={handleClose}>
                  &times;
                </button>
              </div>
            </div>
            <img
              src={modalStreamUrl}
              alt="Live feed"
              className="live-modal-image"
            />
          </div>
        </div>
      )}
    </>
  );
}
