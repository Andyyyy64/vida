import { useState } from 'react';

export function LiveFeed() {
  const [live, setLive] = useState(false);

  return (
    <div className="live-feed">
      <div className={`live-indicator ${live ? 'active' : ''}`}>
        <span className={`live-dot ${live ? '' : 'offline'}`} />
        {live ? 'LIVE' : 'OFFLINE'}
      </div>
      <img
        src="/api/live/stream"
        alt="Live feed"
        className="live-image"
        style={{ display: live ? 'block' : 'none' }}
        onLoad={() => setLive(true)}
        onError={() => setLive(false)}
      />
    </div>
  );
}
