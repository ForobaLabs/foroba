import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Activity, HelpCircle, Lock, Monitor, Moon, Scale, Settings, Sun, User } from 'lucide-react';
import { useTheme, useUserProfile, type SuiteProfile } from '@foroba/ui';

const LANGUAGES = [
  { code: 'en', label: 'EN' },
  { code: 'fr', label: 'FR' },
  { code: 'it', label: 'IT' },
] as const;

const rowClass =
  'flex min-h-[44px] items-center gap-2.5 rounded-lg px-3 text-sm text-[var(--color-text-primary)] no-underline hover:bg-[var(--color-bg-elevated)]';

/** Profile, settings, language and theme — everything that is not a destination. */
export function AccountMenu({ profile }: { profile: SuiteProfile | null }) {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const { updateProfile } = useUserProfile();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [openUp, setOpenUp] = useState(false);
  const panelId = useId();

  // In the mobile More sheet the avatar sits at the bottom edge, so a downward panel would be clipped.
  useLayoutEffect(() => {
    if (!open) return;
    const rect = panelRef.current?.getBoundingClientRect();
    if (rect && rect.bottom > window.innerHeight) setOpenUp(true);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [open]);

  const initials = profile
    ? `${profile.firstName.slice(0, 1)}${profile.lastName.slice(0, 1)}`.toUpperCase() || '?'
    : '?';
  const nextTheme = theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system';
  const ThemeIcon = theme === 'dark' ? Moon : theme === 'light' ? Sun : Monitor;
  const themeLabel =
    theme === 'dark' ? t('sidebar.darkMode') : theme === 'light' ? t('sidebar.lightMode') : t('sidebar.systemMode');
  const close = () => { setOpen(false); };

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-label={t('accountMenu.label')}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => { setOpenUp(false); setOpen((v) => !v); }}
        className="flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-[var(--color-bg-border)] bg-[var(--color-accent-subtle)] text-sm font-semibold text-[var(--color-accent-text)]"
      >
        {profile?.avatarUrl ? (
          <img src={profile.avatarUrl} alt="" className="h-9 w-9 rounded-full object-cover" />
        ) : (
          initials
        )}
      </button>
      {open && (
        <div
          id={panelId}
          ref={panelRef}
          role="dialog"
          aria-label={t('accountMenu.label')}
          className={`absolute right-0 z-50 flex max-h-[calc(100vh-96px)] w-72 max-w-[calc(100vw-32px)] flex-col gap-1 overflow-y-auto rounded-xl ${openUp ? 'bottom-full mb-1' : 'top-full mt-1'} border border-[var(--color-bg-border)] bg-[var(--color-bg-surface)] p-2`}
          style={{ boxShadow: 'var(--shadow-lg)' }}
        >
          <Link to="/profile" className={rowClass} onClick={close}>
            <User size={16} aria-hidden="true" />
            <span className="flex-1 truncate">{t('kelenNav.profile')}</span>
          </Link>
          <Link to="/security" className={rowClass} onClick={close}><Lock size={16} aria-hidden="true" />{t('kelenNav.security')}</Link>
          <Link to="/settings" className={rowClass} onClick={close}><Settings size={16} aria-hidden="true" />{t('kelenNav.settings')}</Link>
          <Link to="/status" className={rowClass} onClick={close}><Activity size={16} aria-hidden="true" />{t('kelenNav.status')}</Link>
          <Link to="/help" className={rowClass} onClick={close}><HelpCircle size={16} aria-hidden="true" />{t('kelenNav.help')}</Link>
          <Link to="/legal" className={rowClass} onClick={close}><Scale size={16} aria-hidden="true" />{t('kelenNav.legal')}</Link>

          <hr className="my-1 border-[var(--color-bg-border)]" />

          <div className="px-3 py-1">
            <div className="mb-1 text-xs uppercase tracking-wider text-[var(--color-text-muted)]">{t('accountMenu.language')}</div>
            <div className="flex gap-1">
              {LANGUAGES.map(({ code, label }) => (
                <button
                  key={code}
                  type="button"
                  aria-pressed={i18n.language === code}
                  onClick={() => {
                    void i18n.changeLanguage(code);
                    // foroba.profile overrides foroba.language on reload, so persist there.
                    updateProfile({ language: code });
                  }}
                  className={`min-h-[44px] flex-1 cursor-pointer rounded-md border text-sm ${
                    i18n.language === code
                      ? 'border-transparent bg-[var(--color-accent)] font-semibold text-[var(--color-accent-fg)]'
                      : 'border-[var(--color-bg-border)] bg-transparent text-[var(--color-text-secondary)]'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <button type="button" onClick={() => { setTheme(nextTheme); }} className={`${rowClass} w-full cursor-pointer border-0 bg-transparent text-left`}>
            <ThemeIcon size={16} aria-hidden="true" />
            {t('accountMenu.appearance')}: {themeLabel}
          </button>

          <p className="px-3 pb-1 pt-2 text-xs text-[var(--color-text-muted)]">{t('accountMenu.dataStays')}</p>
        </div>
      )}
    </div>
  );
}
