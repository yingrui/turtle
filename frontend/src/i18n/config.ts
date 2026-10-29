import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// The strings live in `locales/*.json`: a thousand lines of literals next to code made both harder to
// read, and `scripts/check-i18n.py` can compare two JSON files without parsing TypeScript.
import en from './locales/en.json';
import zhCN from './locales/zh-CN.json';

const resources = {
  en: { translation: en },
  'zh-CN': { translation: zhCN },
};

i18n.use(initReactI18next).init({
  resources,
  lng: 'zh-CN',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export default i18n;
