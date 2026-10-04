import { Card, CardContent } from '@foroba/ui';
import { useQuery } from '@tanstack/react-query';
import { Check, Circle, X } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { fetchPazuruAccounts, fetchPazuruGoals } from '../api/pazuru';
import { useAuth } from '../auth/AuthProvider';
import { buildChecklist, dismiss, isComplete, isDismissed } from '../lib/onboardingChecklist';

/** Getting-started card: verify email, enable MFA, add data, set a goal. Hidden once done or dismissed. */
export function OnboardingChecklist() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [hidden, setHidden] = useState(isDismissed);
  const accounts = useQuery({ queryKey: ['onboarding', 'accounts'], queryFn: fetchPazuruAccounts, retry: false });
  const goals = useQuery({ queryKey: ['onboarding', 'goals'], queryFn: fetchPazuruGoals, retry: false });

  // Unknown counts (loading, step-up pending, outage) must never produce a false "to do".
  if (hidden || !user || !accounts.data || !goals.data) return null;

  const items = buildChecklist({
    emailVerified: user.email_verified !== false,
    mfaEnabled: user.totp_enabled || user.email_otp_enabled || user.webauthn_enabled,
    accountCount: accounts.data.length,
    goalCount: goals.data.length,
  });
  if (isComplete(items)) return null;

  const doneCount = items.filter((i) => i.done).length;

  return (
    <Card className="mt-4">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium text-[var(--color-text-primary)]">{t('onboardingChecklist.title')}</h2>
            <p className="text-xs text-[var(--color-text-muted)]">
              {t('onboardingChecklist.progress', { done: doneCount, total: items.length })}
            </p>
          </div>
          <button
            type="button"
            aria-label={t('onboardingChecklist.dismiss')}
            onClick={() => { dismiss(); setHidden(true); }}
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover,transparent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <ul className="mt-2 flex flex-col">
          {items.map((item) => (
            <li key={item.id}>
              {item.done ? (
                <span className="flex min-h-11 items-center gap-2 text-sm text-[var(--color-text-muted)] line-through">
                  <Check size={16} aria-hidden="true" className="text-[var(--color-success,#16a34a)]" />
                  {t(`onboardingChecklist.items.${item.id}`)}
                </span>
              ) : (
                <Link
                  to={item.to}
                  className="flex min-h-11 items-center gap-2 text-sm text-[var(--color-text-primary)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
                >
                  <Circle size={16} aria-hidden="true" className="text-[var(--color-text-muted)]" />
                  {t(`onboardingChecklist.items.${item.id}`)}
                </Link>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
