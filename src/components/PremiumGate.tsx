import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { EmptyState, LockedFeatureCard } from '@foroba/ui';

interface PremiumGateProps {
  visible: boolean;
  unlocked: boolean;
  /** Page/feature name, shown as the card heading. */
  feature: string;
  /** One line: what the user gets once unlocked. */
  description: string;
  children: ReactNode;
}

/**
 * Locked-feature gate for premium pages: renders children when unlocked, otherwise a
 * LockedFeatureCard. Payments are not live, so the CTA explains that instead of promising a trial.
 */
export function PremiumGate({ visible, unlocked, feature, description, children }: PremiumGateProps) {
  const { t } = useTranslation();
  const [noticed, setNoticed] = useState(false);
  if (!visible) {
    return (
      <>
        <EmptyState
          title={feature}
          message={t('premium.hidden')}
          action={
            <Link
              to="/"
              className="inline-flex min-h-11 items-center justify-center rounded-lg bg-[var(--color-accent)] px-4 text-sm font-semibold text-[var(--color-accent-fg,#fff)] hover:opacity-90"
            >
              {t('notFound.home')}
            </Link>
          }
        />
      </>
    );
  }
  if (unlocked) return <>{children}</>;
  return (
    <div className="mx-auto max-w-lg">
      <LockedFeatureCard
        feature={feature}
        description={description}
        pillLabel={t('premium.pill')}
        ctaLabel={t('premium.cta')}
        onCta={() => setNoticed(true)}
      />
      {noticed && (
        <p role="status" className="mt-3 text-center text-sm text-[var(--color-text-secondary)]">
          {t('premium.soon')}
        </p>
      )}
    </div>
  );
}
