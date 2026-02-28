import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';
import { todayStr } from '../lib/date';

export function useDailyMemo(date: string) {
  const [content, setContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestContent = useRef(content);

  const readonly = date !== todayStr();

  // Fetch memo when date changes
  useEffect(() => {
    setLoaded(false);
    api.memos.get(date)
      .then((memo) => {
        setContent(memo.content);
        latestContent.current = memo.content;
      })
      .catch(() => {
        setContent('');
        latestContent.current = '';
      })
      .finally(() => setLoaded(true));
  }, [date]);

  // Debounced save
  const updateContent = useCallback((value: string) => {
    setContent(value);
    latestContent.current = value;

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setSaving(true);
      api.memos.put(date, value)
        .catch(console.error)
        .finally(() => setSaving(false));
    }, 1000);
  }, [date]);

  // Cleanup timer on unmount or date change
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [date]);

  return { content, updateContent, saving, readonly, loaded };
}
