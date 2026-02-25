import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import type { Frame } from '../lib/types';

export function useFrames(date: string) {
  const [frames, setFrames] = useState<Frame[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!date) return;
    setLoading(true);
    api.frames
      .list(date)
      .then(setFrames)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [date]);

  return { frames, loading };
}
