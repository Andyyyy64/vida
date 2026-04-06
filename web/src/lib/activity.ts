/**
 * Shared activity module — single source of truth for meta-category colors,
 * labels, and dynamic activity->meta_category mapping from the API.
 */

import { api } from './api';

export const META_COLORS: Record<string, string> = {
  focus: '#60a860',
  communication: '#6088d0',
  entertainment: '#d06060',
  browsing: '#d0a840',
  break: '#888888',
  idle: '#444466',
  other: '#a060b0',
};

// i18n keys for meta-category labels — use t(`activity.${key}`) for display
export const META_LABEL_KEYS: Record<string, string> = {
  focus: 'activity.focus',
  communication: 'activity.communication',
  entertainment: 'activity.entertainment',
  browsing: 'activity.browsing',
  break: 'activity.break',
  idle: 'activity.idle',
  other: 'activity.other',
};

// Dynamic mappings fetched from API
let _mappings: Record<string, string> | null = null;

export async function loadActivityMappings(): Promise<void> {
  try {
    _mappings = await api.activities.mappings();
  } catch {
    // Silently fail — will use 'other' as fallback
  }
}

export function getMetaCategory(activity: string): string {
  if (!activity) return 'other';
  if (_mappings && activity in _mappings) return _mappings[activity];
  return 'other';
}

export function activityColor(activity: string): string {
  return META_COLORS[getMetaCategory(activity)] || META_COLORS.other;
}
