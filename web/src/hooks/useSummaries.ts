import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api';
import { todayStr } from '../lib/date';
import { getLiveDataPollInterval } from '../lib/demo-runtime';
import { getRuntime } from '../lib/runtime';
import { useToast } from './useToast';
import type { Summary } from '../lib/types';

export function useSummaries(date: string, scale?: string) {
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();
  const { t } = useTranslation();
  const isDemo = getRuntime().isDemo;

  const fetchSummaries = useCallback(() => {
    if (!date) return;
    api.summaries
      .list(date, scale)
      .then(setSummaries)
      .catch(() => {
        addToast(t('errors.fetchSummaries'), 'error');
      });
  }, [date, scale, addToast, t]);

  useEffect(() => {
    if (!date) return;
    setLoading(true);
    api.summaries
      .list(date, scale)
      .then(setSummaries)
      .catch(() => {
        addToast(t('errors.fetchSummaries'), 'error');
      })
      .finally(() => setLoading(false));
  }, [date, scale, addToast, t]);

  useEffect(() => {
    if (!date) return;
    const isToday = date === todayStr();
    if (!isDemo && !isToday) return;

    const id = setInterval(fetchSummaries, getLiveDataPollInterval(isDemo));
    return () => clearInterval(id);
  }, [date, fetchSummaries, isDemo]);

  // Listen for WebSocket-triggered refreshes
  useEffect(() => {
    const handler = () => fetchSummaries();
    window.addEventListener('vida:refresh-summaries', handler);
    return () => window.removeEventListener('vida:refresh-summaries', handler);
  }, [fetchSummaries]);

  return { summaries, loading, refresh: fetchSummaries };
}
