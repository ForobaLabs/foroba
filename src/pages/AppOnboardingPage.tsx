import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { useLanguage, useTheme, useUserProfile } from '@foroba/ui';
import { completeOnboarding } from '../auth/api';

type Lang = 'en' | 'it' | 'fr';
type Theme = 'system' | 'light' | 'dark';

const STEPS = ['welcome', 'account', 'networth'] as const;
const LANGUAGES: { value: Lang; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'it', label: 'Italiano' },
  { value: 'fr', label: 'Français' },
];

const field =
  'mt-1 block min-h-11 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3 text-base text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]';
const primary =
  'inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-[var(--color-accent)] px-4 text-sm font-semibold text-[var(--color-accent-fg,#fff)] hover:opacity-90';
const secondary =
  'inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-[var(--color-border)] px-4 text-sm font-medium text-[var(--color-text-primary)] hover:bg-[var(--color-bg-elevated)]';
const ghost =
  'inline-flex min-h-11 items-center justify-center rounded-lg px-4 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)]';

export function AppOnboardingPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { setLanguage } = useLanguage();
  const { theme, setTheme } = useTheme();
  const { updateProfile } = useUserProfile();
  const [step, setStep] = useState(0);
  const current = STEPS[step];
  const lang = (['en', 'it', 'fr'].includes(i18n.language) ? i18n.language : 'en') as Lang;

  const pickLanguage = (next: Lang) => {
    void i18n.changeLanguage(next);
    setLanguage(next);
    // App.tsx drives i18n from foroba.profile, so the profile must carry the choice too.
    updateProfile({ language: next });
  };

  const finish = () => {
    localStorage.setItem('foroba.onboarding.done', '1');
    void completeOnboarding();
    navigate('/');
  };
  // Hand-off links leave the SPA, so mark onboarding done before following them.
  const markDone = () => {
    localStorage.setItem('foroba.onboarding.done', '1');
    void completeOnboarding();
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center gap-6 p-4">
      <div
        role="progressbar"
        aria-label={t('onboarding.progress', { current: step + 1, total: STEPS.length })}
        aria-valuemin={1}
        aria-valuemax={STEPS.length}
        aria-valuenow={step + 1}
        className="flex gap-2"
      >
        {STEPS.map((s, i) => (
          <span
            key={s}
            aria-hidden="true"
            className={`h-1.5 flex-1 rounded-full ${i <= step ? 'bg-[var(--color-accent)]' : 'bg-[var(--color-bg-elevated)]'}`}
          />
        ))}
      </div>
      <p className="text-xs text-[var(--color-text-muted)]">
        {t('onboarding.progress', { current: step + 1, total: STEPS.length })}
      </p>

      <section aria-label={t('onboarding.label')} className="flex flex-col gap-3">
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">{t(`onboarding.${current}.title`)}</h1>
        <p className="text-[var(--color-text-secondary)]">{t(`onboarding.${current}.body`)}</p>

        {current === 'welcome' && (
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="ob-language" className="text-sm font-medium text-[var(--color-text-secondary)]">
                {t('onboarding.language')}
              </label>
              <select id="ob-language" className={field} value={lang} onChange={(e) => pickLanguage(e.target.value as Lang)}>
                {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="ob-theme" className="text-sm font-medium text-[var(--color-text-secondary)]">
                {t('onboarding.theme')}
              </label>
              <select id="ob-theme" className={field} value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
                <option value="system">{t('onboarding.themeSystem')}</option>
                <option value="light">{t('onboarding.themeLight')}</option>
                <option value="dark">{t('onboarding.themeDark')}</option>
              </select>
            </div>
          </div>
        )}

        {current === 'account' && (
          <div className="mt-2 flex flex-col gap-3">
            <a className={primary} href="/foroba-api/auth/handoff/pazuru?redirect=/settings" onClick={markDone}>
              {t('onboarding.bank')}
            </a>
            <a className={secondary} href="/foroba-api/auth/handoff/tsumi?redirect=/settings" onClick={markDone}>
              {t('onboarding.portfolio')}
            </a>
            <p className="text-xs text-[var(--color-text-muted)]">{t('onboarding.later')}</p>
          </div>
        )}
      </section>

      <div className="flex flex-col gap-2">
        {current === 'welcome' && (
          <button type="button" className={primary} onClick={() => setStep(1)}>{t('onboarding.welcome.action')}</button>
        )}
        {current === 'account' && (
          <button type="button" className={ghost} onClick={() => setStep(2)}>{t('onboarding.skip')}</button>
        )}
        {current === 'networth' && (
          <button type="button" className={primary} onClick={finish}>{t('onboarding.networth.action')}</button>
        )}
        {current === 'welcome' && (
          <button type="button" className={ghost} onClick={finish}>{t('onboarding.skip')}</button>
        )}
      </div>
    </main>
  );
}
