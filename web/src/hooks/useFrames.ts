import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api';
import { todayStr } from '../lib/date';
import { getLiveDataPollInterval } from '../lib/demo-runtime';
import { getRuntime } from '../lib/runtime';
import { useToast } from './useToast';
import type { Frame } from '../lib/types';

export function useFrames(date: string) {
  const [frames, setFrames] = useState<Frame[]>([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();
  const { t } = useTranslation();
  const isDemo = getRuntime().isDemo;

  const fetchFrames = useCallback(() => {
    if (!date) return;
    api.frames
      .list(date)
      .then(setFrames)
      .catch(() => {
        addToast(t('errors.fetchFrames'), 'error');
      });
  }, [date, addToast, t]);

  useEffect(() => {
    if (!date) return;
    setLoading(true);
    api.frames
      .list(date)
      .then(setFrames)
      .catch(() => {
        addToast(t('errors.fetchFrames'), 'error');
      })
      .finally(() => setLoading(false));
  }, [date, addToast, t]);

  // Poll for new data
  useEffect(() => {
    if (!date) return;
    const isToday = date === todayStr();
    if (!isDemo && !isToday) return;

    const id = setInterval(fetchFrames, getLiveDataPollInterval(isDemo));
    return () => clearInterval(id);
  }, [date, fetchFrames, isDemo]);

  // Listen for WebSocket-triggered refreshes
  useEffect(() => {
    const handler = () => fetchFrames();
    window.addEventListener('vida:refresh-frames', handler);
    return () => window.removeEventListener('vida:refresh-frames', handler);
  }, [fetchFrames]);

  return { frames, loading, refresh: fetchFrames };
}
