import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { en, fr, it } from '@foroba/ui/i18n';

const savedLang = typeof localStorage !== 'undefined'
  ? (localStorage.getItem('foroba.language') ?? 'en')
  : 'en';

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    fr: { translation: fr },
    it: { translation: it },
  },
  lng: savedLang,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export default i18n;
