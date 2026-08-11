import {
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  ExportButton,
  KpiCard,
  LoadingState,
  PageContainer,
  SectionHeader,
} from '@foroba/ui';
import { useNavigate } from 'react-router';
import { useAccountsList, usePazuruHealth } from '../hooks/useServiceHealth';

const BANK_LABELS: Record<string, string> = {
  revolut: 'Revolut',
  bnl: 'BNL',
  boursorama: 'Boursorama',
  hype: 'Hype',
};

const PAZURU_APP_URL = import.meta.env.VITE_PAZURU_APP_URL ?? 'http://localhost:5173';

function ConnectBankButton({ variant }: { variant?: 'outline' }) {
  return (
    <a href={`${PAZURU_APP_URL}/settings`}>
      <Button variant={variant}>🏦 Connect a bank</Button>
    </a>
  );
}

export function AccountsPage() {
  const health = usePazuruHealth();
  const online = health.data?.status === 'ok';
  const accounts = useAccountsList();
  const navigate = useNavigate();

  return (
    <PageContainer>
      <div className="flex items-start justify-between mb-6">
        <SectionHeader
          title="Accounts"
          description="Bank accounts & cashflow powered by Pazuru"
        />
        {online && (
          <div className="flex items-center gap-2">
            <ConnectBankButton variant="outline" />
            <ExportButton onExport={(fmt) => { window.location.href = `/pazuru-api/export/transactions?format=${fmt}`; }} />
          </div>
        )}
      </div>

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
          action={<ConnectBankButton />}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <KpiCard
            label="Total"
            value={
              new Set(accounts.data.map((a) => a.currency)).size === 1
                ? new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: accounts.data[0].currency,
                  }).format(accounts.data.reduce((sum, a) => sum + a.balance, 0))
                : accounts.data.reduce((sum, a) => sum + a.balance, 0).toFixed(2)
            }
            subtitle={
              new Set(accounts.data.map((a) => a.currency)).size === 1
                ? undefined
                : 'Mixed currencies'
            }
          />
          {accounts.data.map((acc) => (
            <button
              key={acc.id}
              type="button"
              onClick={() => navigate(`/accounts/${acc.id}`)}
              className="text-left"
            >
              <KpiCard
                label={`${BANK_LABELS[acc.bankName] ?? acc.bankName} — ${acc.displayName}`}
                value={new Intl.NumberFormat('en-US', {
                  style: 'currency',
                  currency: acc.currency,
                }).format(acc.balance)}
              />
            </button>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
