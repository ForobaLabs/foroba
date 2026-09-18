/**
 * CL-2.1 — Re-consent gate. Shown when the backend reports a stale consent
 * (TOS or Privacy Policy was updated since the user last accepted).
 * The user must accept all stale documents before using the app.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { fetchConsentStatus, postConsentAccept } from '../auth/api';
import { PRIVACY_POLICY, TERMS_OF_SERVICE } from '../data/legal';

export function ReConsentPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Routing gap: /re-consent is a top-level sibling of <App> (router.tsx), with no
  // self-guard of its own, so an already-fully-consented user landing here directly
  // (stale bookmark, back button, etc.) would otherwise see the form again for no
  // reason. Shares App.tsx's exact ['consents-status'] queryKey/cache.
  const { data: consentStatus } = useQuery({
    queryKey: ['consents-status'],
    queryFn: fetchConsentStatus,
  });

  useEffect(() => {
    if (consentStatus && Object.values(consentStatus).every(Boolean)) {
      navigate('/', { replace: true });
    }
  }, [consentStatus, navigate]);

  async function handleAccept() {
    if (!checked) return;
    setSubmitting(true);
    setError(null);
    try {
      await postConsentAccept(['terms_of_service', 'privacy_policy']);
      // Set the cache synchronously instead of invalidateQueries(): /re-consent is a
      // top-level sibling route of <App>, so App.tsx's ['consents-status'] query has
      // no active observer while mounted here -- invalidation only marks it stale,
      // it doesn't refetch. Without this, <App>'s first render after navigate() below
      // would read the still-stale cached value and bounce straight back (FOR-D07).
      queryClient.setQueryData(['consents-status'], {
        terms_of_service: true,
        privacy_policy: true,
      });
      navigate('/', { replace: true });
    } catch {
      setError('Failed to record your consent. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-primary)] p-6">
      <div className="w-full max-w-xl rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 shadow-lg">
        <h1 className="mb-2 text-xl font-semibold text-[var(--color-text-primary)]">
          Updated legal documents
        </h1>
        <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
          Our Terms of Service or Privacy Policy have been updated since your last visit.
          Please review and accept them to continue using Foroba.
        </p>

        <div className="mb-4 max-h-48 overflow-y-auto rounded border border-[var(--color-border)] bg-[var(--color-bg-primary)] p-4 text-xs text-[var(--color-text-secondary)]">
          <h2 className="mb-2 font-semibold">{TERMS_OF_SERVICE.title} (excerpt)</h2>
          <p className="whitespace-pre-wrap">{TERMS_OF_SERVICE.content.slice(0, 800)}…</p>
        </div>

        <div className="mb-6 max-h-48 overflow-y-auto rounded border border-[var(--color-border)] bg-[var(--color-bg-primary)] p-4 text-xs text-[var(--color-text-secondary)]">
          <h2 className="mb-2 font-semibold">{PRIVACY_POLICY.title} (excerpt)</h2>
          <p className="whitespace-pre-wrap">{PRIVACY_POLICY.content.slice(0, 800)}…</p>
        </div>

        <label className="mb-6 flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 accent-[var(--color-accent)]"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
          />
          <span className="text-sm text-[var(--color-text-primary)]">
            I have read and agree to the updated Terms of Service and Privacy Policy.
          </span>
        </label>

        {error && (
          <p className="mb-4 text-sm text-[var(--color-negative)]">{error}</p>
        )}

        <button
          onClick={handleAccept}
          disabled={!checked || submitting}
          className="w-full rounded-lg bg-[var(--color-accent)] px-4 py-2.5 text-sm font-medium text-white transition-opacity disabled:opacity-40"
        >
          {submitting ? 'Saving…' : 'Accept and continue'}
        </button>
      </div>
    </div>
  );
}
