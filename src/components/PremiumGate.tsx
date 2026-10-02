import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { LockedFeatureCard } from '@foroba/ui';

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
  if (!visible) return null;
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
