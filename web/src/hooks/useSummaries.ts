import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import type { Summary } from '../lib/types';

export function useSummaries(date: string, scale?: string) {
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!date) return;
    setLoading(true);
    api.summaries
      .list(date, scale)
      .then(setSummaries)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [date, scale]);

  return { summaries, loading };
}
