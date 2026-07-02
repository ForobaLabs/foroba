import {
  Badge,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  KpiCard,
  LoadingState,
  PageContainer,
  SectionHeader,
} from '@foroba/ui';
import { useAccountsList, usePazuruHealth } from '../hooks/useServiceHealth';

const BANK_LABELS: Record<string, string> = {
  revolut: 'Revolut',
  bnl: 'BNL',
  boursorama: 'Boursorama',
  hype: 'Hype',
};

export function AccountsPage() {
  const health = usePazuruHealth();
  const online = health.data?.status === 'ok';
  const accounts = useAccountsList();

  return (
    <PageContainer>
      <SectionHeader
        title="Accounts"
        description="Bank accounts & cashflow powered by Pazuru"
        className="mb-6"
      />

      {!online ? (
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-sm font-medium text-[var(--color-text-primary)]">Pazuru status</span>
              <Badge variant="warning">Offline</Badge>
            </div>
            <p className="text-sm text-[var(--color-text-muted)]">
              Pazuru is not reachable. Start it at{' '}
              <code className="rounded bg-[var(--color-bg-elevated)] px-1 text-xs">
                {import.meta.env.VITE_PAZURU_API_URL ?? 'http://localhost:8000'}
              </code>{' '}
              to see your accounts here.
            </p>
          </CardContent>
        </Card>
      ) : accounts.isLoading ? (
        <LoadingState message="Loading accounts…" />
      ) : accounts.isError ? (
        <ErrorState
          message="Could not load accounts from Pazuru."
          onRetry={() => accounts.refetch()}
        />
      ) : !accounts.data || accounts.data.length === 0 ? (
        <EmptyState
          title="No accounts connected"
          message="Connect a bank in Pazuru to see your accounts here."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {accounts.data.map((acc) => (
            <KpiCard
              key={acc.id}
              label={`${BANK_LABELS[acc.bankName] ?? acc.bankName} — ${acc.displayName}`}
              value={new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: acc.currency,
              }).format(acc.balance)}
            />
          ))}
        </div>
      )}
    </PageContainer>
  );
}
