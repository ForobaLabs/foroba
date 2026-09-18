import { useState, type FormEvent } from 'react';
import {
  Button,
  EmptyState,
  ErrorState,
  FormField,
  Input,
  LoadingState,
  PageContainer,
  SectionHeader,
  Switch,
} from '@foroba/ui';
import { useHousehold } from '../auth/useHousehold';

const SHARE_RESOURCE_TYPES: { key: string; label: string; description: string }[] = [
  { key: 'accounts', label: 'Bank accounts', description: 'Pazuru accounts and balances' },
  { key: 'goals', label: 'Goals', description: 'Pazuru savings and spending goals' },
  { key: 'budgets', label: 'Budgets', description: 'Pazuru budget categories and limits' },
  { key: 'portfolio', label: 'Portfolio', description: 'Tsumi ETF and crypto positions' },
];

export function HouseholdPage() {
  const { household, join, acceptInvite, leave, toggleShare } = useHousehold();
  const [email, setEmail] = useState('');
  const [joinError, setJoinError] = useState<string | null>(null);
  const [joinSent, setJoinSent] = useState(false);
  const [inviteToken, setInviteToken] = useState('');
  const [acceptError, setAcceptError] = useState<string | null>(null);

  const handleJoin = async (e: FormEvent) => {
    e.preventDefault();
    setJoinError(null);
    try {
      // FOR-D04: this only sends a consent-requiring invite -- the target
      // must accept it (see "Accept an invite" below) before any merge
      // happens, so there is no household to show here yet.
      await join.mutateAsync(email);
      setEmail('');
      setJoinSent(true);
    } catch (err) {
      setJoinError(err instanceof Error ? err.message : 'Failed to send join request');
    }
  };

  const handleAcceptInvite = async (e: FormEvent) => {
    e.preventDefault();
    setAcceptError(null);
    try {
      await acceptInvite.mutateAsync(inviteToken);
      setInviteToken('');
    } catch (err) {
      setAcceptError(err instanceof Error ? err.message : 'Failed to accept invite');
    }
  };

  return (
    <PageContainer>
      <SectionHeader
        title="Household"
        description="Share select data with household members you trust — everything is private by default"
        className="mb-6"
      />
      <div className="mx-auto max-w-lg">
        {household.isLoading ? (
          <LoadingState message="Loading household…" />
        ) : household.isError || !household.data ? (
          <ErrorState
            message="Could not load your household."
            onRetry={() => household.refetch()}
          />
        ) : (
          <>
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
              {household.data.household_id ? (
                <>
                  <h3 className="mb-3 text-sm font-medium text-[var(--color-text-primary)]">
                    Members
                  </h3>
                  <ul className="mb-4 flex flex-col gap-2">
                    {household.data.members.map((m) => (
                      <li
                        key={m.id}
                        className="flex items-center justify-between rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm"
                      >
                        <span className="text-[var(--color-text-primary)]">{m.name}</span>
                        <span className="text-[var(--color-text-muted)]">{m.email}</span>
                      </li>
                    ))}
                  </ul>
                  <Button
                    variant="secondary"
                    onClick={() => leave.mutate()}
                    disabled={leave.isPending}
                  >
                    {leave.isPending ? 'Leaving…' : 'Leave household'}
                  </Button>
                </>
              ) : (
                <EmptyState
                  title="No household yet"
                  message="Send a join request to someone already in a household, or invite someone by email — either way, they must accept before anything is shared."
                />
              )}

              <form onSubmit={handleJoin} className="mt-6 flex flex-col gap-3">
                <FormField label="Join by email" htmlFor="household-join-email">
                  <Input
                    id="household-join-email"
                    type="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      setJoinSent(false);
                    }}
                    placeholder="member@example.com"
                    required
                  />
                </FormField>
                <p className="text-xs text-[var(--color-text-muted)]">
                  This sends a request — they must accept it before you're merged into one
                  household.
                </p>
                {joinError && (
                  <p className="text-xs text-[var(--color-negative)]" role="alert">
                    {joinError}
                  </p>
                )}
                {joinSent && !joinError && (
                  <p className="text-xs text-[var(--color-positive)]">
                    Request sent — waiting for them to accept.
                  </p>
                )}
                <Button type="submit" disabled={join.isPending || !email}>
                  {join.isPending ? 'Sending…' : 'Send join request'}
                </Button>
              </form>

              <form onSubmit={handleAcceptInvite} className="mt-6 flex flex-col gap-3">
                <FormField label="Accept an invite" htmlFor="household-invite-token">
                  <Input
                    id="household-invite-token"
                    type="text"
                    value={inviteToken}
                    onChange={(e) => setInviteToken(e.target.value)}
                    placeholder="Code from your invite email"
                    required
                  />
                </FormField>
                {acceptError && (
                  <p className="text-xs text-[var(--color-negative)]" role="alert">
                    {acceptError}
                  </p>
                )}
                <Button
                  type="submit"
                  variant="secondary"
                  disabled={acceptInvite.isPending || !inviteToken}
                >
                  {acceptInvite.isPending ? 'Accepting…' : 'Accept invite'}
                </Button>
              </form>
            </div>

            <div className="mt-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
              <h3 className="mb-1 text-sm font-medium text-[var(--color-text-primary)]">
                Sharing preferences
              </h3>
              <p className="mb-4 text-xs text-[var(--color-text-muted)]">
                Turn on sharing per category to make your data visible to household members.
                Everything is private until you opt in.
              </p>
              <ul className="flex flex-col gap-4">
                {SHARE_RESOURCE_TYPES.map((r) => (
                  <li key={r.key} className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm text-[var(--color-text-primary)]">{r.label}</p>
                      <p className="text-xs text-[var(--color-text-muted)]">{r.description}</p>
                    </div>
                    <Switch
                      checked={household.data.share_preferences[r.key] ?? false}
                      disabled={!household.data.household_id || toggleShare.isPending}
                      onCheckedChange={(checked) =>
                        toggleShare.mutate({ resourceType: r.key, shared: checked })
                      }
                    />
                  </li>
                ))}
              </ul>
            </div>

            <p className="mt-4 text-center text-xs text-[var(--color-text-muted)]">
              Sharing is opt-in per category — nothing is shared until you switch it on.
            </p>
          </>
        )}
      </div>
    </PageContainer>
  );
}
