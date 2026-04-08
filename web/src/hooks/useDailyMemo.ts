import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';
import { todayStr } from '../lib/date';
import { getRuntime } from '../lib/runtime';

export function useDailyMemo(date: string) {
  const [content, setContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestContent = useRef(content);
  const dirtyRef = useRef(false);

  const isDemo = getRuntime().isDemo;
  const readonly = isDemo || date !== todayStr();

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
    dirtyRef.current = true;

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      dirtyRef.current = false;
      setSaving(true);
      api.memos.put(date, value)
        .catch(console.error)
        .finally(() => setSaving(false));
    }, 1000);
  }, [date]);

  // Flush pending save on date change or unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (dirtyRef.current) {
        dirtyRef.current = false;
        api.memos.put(date, latestContent.current).catch(console.error);
      }
    };
  }, [date]);

  return { content, updateContent, saving, readonly, loaded };
}
