import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import ja from './locales/ja.json';
import en from './locales/en.json';

export const LOCALE_MAP: Record<string, string> = {
  ja: 'ja-JP',
  en: 'en-US',
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      ja: { translation: ja },
      en: { translation: en },
    },
    fallbackLng: 'ja',
    interpolation: {
      // Escape HTML in all interpolated values. Translations MUST NOT
      // contain raw HTML rendered via dangerouslySetInnerHTML — render
      // them as text nodes instead, which React escapes automatically.
      escapeValue: true,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
  });

export default i18n;
