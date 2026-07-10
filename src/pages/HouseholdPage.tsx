import { FormEvent, useState } from 'react';
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
  const { household, join, leave, toggleShare } = useHousehold();
  const [email, setEmail] = useState('');
  const [joinError, setJoinError] = useState<string | null>(null);

  const handleJoin = async (e: FormEvent) => {
    e.preventDefault();
    setJoinError(null);
    try {
      await join.mutateAsync(email);
      setEmail('');
    } catch (err) {
      setJoinError(err instanceof Error ? err.message : 'Failed to join household');
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
                  message="Join a household by entering the email of a member already in one, or invite someone by sharing your email with them."
                />
              )}

              <form onSubmit={handleJoin} className="mt-6 flex flex-col gap-3">
                <FormField label="Join by email" htmlFor="household-join-email">
                  <Input
                    id="household-join-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="member@example.com"
                    required
                  />
                </FormField>
                {joinError && (
                  <p className="text-xs text-[var(--color-negative)]" role="alert">
                    {joinError}
                  </p>
                )}
                <Button type="submit" disabled={join.isPending || !email}>
                  {join.isPending ? 'Joining…' : 'Join household'}
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
