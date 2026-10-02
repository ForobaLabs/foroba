import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { en, fr, it } from '@foroba/ui/i18n';
import kelenEn from './i18n/kelen-en.json';
import kelenFr from './i18n/kelen-fr.json';
import kelenIt from './i18n/kelen-it.json';

const savedLang = typeof localStorage !== 'undefined'
  ? (localStorage.getItem('foroba.language') ?? 'en')
  : 'en';

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: { ...en, ...kelenEn } },
    fr: { translation: { ...fr, ...kelenFr } },
    it: { translation: { ...it, ...kelenIt } },
  },
  lng: savedLang,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

// WCAG 3.1.1: keep <html lang> in step with the UI language, including routes rendered outside <App>.
const syncHtmlLang = (lng: string) => {
  if (typeof document !== 'undefined') document.documentElement.lang = lng;
};
syncHtmlLang(i18n.language);
i18n.on('languageChanged', syncHtmlLang);

export default i18n;
