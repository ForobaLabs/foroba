import { describe, expect, it } from 'vitest';
import i18n from './i18n';

// WCAG 3.1.1: screen readers pick the voice from <html lang>, so it must follow the UI language.
describe('html lang follows the UI language', () => {
  it('updates document.documentElement.lang on every language change', async () => {
    await i18n.changeLanguage('it');
    expect(document.documentElement.lang).toBe('it');
    await i18n.changeLanguage('fr');
    expect(document.documentElement.lang).toBe('fr');
    await i18n.changeLanguage('en');
    expect(document.documentElement.lang).toBe('en');
  });

  it('is set at load time from the stored language', () => {
    expect(document.documentElement.lang).toBe(i18n.language);
  });
});
