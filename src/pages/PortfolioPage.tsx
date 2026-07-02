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
import { usePortfolioPositions, useTsumiHealth } from '../hooks/useServiceHealth';

export function PortfolioPage() {
  const health = useTsumiHealth();
  const online = health.data?.status === 'ok';
  const positions = usePortfolioPositions();

  return (
    <PageContainer>
      <SectionHeader
        title="Portfolio"
        description="ETF & crypto positions powered by Tsumi"
        className="mb-6"
      />

      {!online ? (
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-sm font-medium text-[var(--color-text-primary)]">Tsumi status</span>
              <Badge variant="warning">Offline</Badge>
            </div>
            <p className="text-sm text-[var(--color-text-muted)]">
              Tsumi is not reachable. Start it at{' '}
              <code className="rounded bg-[var(--color-bg-elevated)] px-1 text-xs">
                {import.meta.env.VITE_TSUMI_API_URL ?? 'http://localhost:8050'}
              </code>{' '}
              to see your portfolio here.
            </p>
          </CardContent>
        </Card>
      ) : positions.isLoading ? (
        <LoadingState message="Loading portfolio…" />
      ) : positions.isError ? (
        <ErrorState
          message="Could not load portfolio positions from Tsumi."
          onRetry={() => positions.refetch()}
        />
      ) : !positions.data || positions.data.length === 0 ? (
        <EmptyState
          title="No positions yet"
          message="Add a position in Tsumi to see your portfolio here."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {positions.data.map((p) => (
            <KpiCard
              key={`${p.source}-${p.isin}`}
              label={`${p.name} (${p.isin})`}
              value={new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: p.currency,
              }).format(p.valueEur)}
              delta={p.pnlEur}
              deltaPct={p.pnlPct}
              subtitle={`${p.quantity} · ${p.source}`}
            />
          ))}
        </div>
      )}
    </PageContainer>
  );
}
