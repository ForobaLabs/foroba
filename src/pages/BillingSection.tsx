import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

interface BillingStatus {
  enabled: boolean;
  subscription: { status: string; current_period_end: string | null; cancel_at_period_end: boolean } | null;
}

async function fetchStatus(): Promise<BillingStatus> {
  const res = await fetch('/jeli/billing/status', { credentials: 'include' });
  if (!res.ok) throw new Error(`billing status ${res.status}`);
  return res.json();
}

// Payments are handled by the provider's hosted checkout; the plan is granted only when the
// server receives the provider's signed webhook, never from anything this page sends.
export function BillingSection() {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const { data } = useQuery({ queryKey: ['billing-status'], queryFn: fetchStatus, retry: false });
  if (!data) return null;

  async function upgrade() {
    setBusy(true);
    setError(false);
    try {
      const res = await fetch('/jeli/billing/checkout-session', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: 'premium_monthly' }),
      });
      const body = res.ok ? await res.json() : null;
      if (typeof body?.url === 'string' && body.url.startsWith('https://')) {
        window.location.assign(body.url);
        return;
      }
      setError(true);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  const sub = data.subscription;
  return (
    <section className="mb-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6" aria-labelledby="billing-title">
      <h2 id="billing-title" className="mb-2 text-base font-semibold">{t('billing.title')}</h2>
      {!data.enabled ? (
        <p className="text-sm text-[var(--color-text-muted)]">{t('billing.unavailable')}</p>
      ) : sub ? (
        <p className="text-sm">
          {t('billing.status', { status: sub.status })}
          {sub.cancel_at_period_end ? ` ${t('billing.cancelsAtEnd')}` : ''}
        </p>
      ) : (
        <>
          <button
            onClick={upgrade}
            disabled={busy}
            className="min-h-11 rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {t('billing.upgrade')}
          </button>
          {error && <p role="alert" className="mt-2 text-sm text-[var(--color-danger,#dc2626)]">{t('billing.error')}</p>}
        </>
      )}
    </section>
  );
}
