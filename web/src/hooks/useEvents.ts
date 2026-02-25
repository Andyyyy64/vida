import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import type { Event } from '../lib/types';

export function useEvents(date: string) {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!date) return;
    setLoading(true);
    api.events
      .list(date)
      .then(setEvents)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [date]);

  return { events, loading };
}
