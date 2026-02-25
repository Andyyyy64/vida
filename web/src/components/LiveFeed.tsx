import { useState, useEffect, useRef } from 'react';

export function LiveFeed() {
  const [src, setSrc] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    const fetchFrame = () => {
      setSrc(`/api/live/frame?t=${Date.now()}`);
    };

    fetchFrame();
    intervalRef.current = window.setInterval(fetchFrame, 5000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return (
    <div className="live-feed">
      <div className={`live-indicator ${live ? 'active' : ''}`}>
        <span className={`live-dot ${live ? '' : 'offline'}`} />
        {live ? 'LIVE' : 'OFFLINE'}
      </div>
      {src && (
        <img
          src={src}
          alt="Live feed"
          className="live-image"
          style={{ display: live ? 'block' : 'none' }}
          onLoad={() => setLive(true)}
          onError={() => setLive(false)}
        />
      )}
    </div>
  );
}
