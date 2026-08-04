import {
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  KpiCard,
  LoadingState,
  PageContainer,
  SectionHeader,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@foroba/ui';
import { useNavigate } from 'react-router';
import type { PortfolioAllocationGroup } from '../api/tsumi';
import {
  usePortfolioAllocations,
  usePortfolioPositions,
  usePortfolioSummary,
  useTsumiHealth,
} from '../hooks/useServiceHealth';

const TSUMI_APP_URL = import.meta.env.VITE_TSUMI_APP_URL ?? 'http://localhost:5178';
const DEPLOYMENT_MODE = import.meta.env.VITE_DEPLOYMENT_MODE ?? 'selfhost';

function ConnectInvestmentButton({ variant }: { variant?: 'outline' }) {
  return (
    <a href={`${TSUMI_APP_URL}/settings`}>
      <Button variant={variant}>📈 Add a connection</Button>
    </a>
  );
}

function formatCurrency(amount: number, currency = 'EUR') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
}

function AllocationTable({ title, groups }: { title: string; groups: PortfolioAllocationGroup[] }) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-[var(--color-text-primary)]">{title}</p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Label</TableHead>
            <TableHead className="text-right">Value</TableHead>
            <TableHead className="text-right">%</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {groups.map((g) => (
            <TableRow key={g.label}>
              <TableCell>{g.label}</TableCell>
              <TableCell className="text-right">{formatCurrency(g.valueEur)}</TableCell>
              <TableCell className="text-right">{g.pct.toFixed(1)}%</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function PortfolioPage() {
  const health = useTsumiHealth();
  const online = health.data?.status === 'ok';
  const summary = usePortfolioSummary();
  const positions = usePortfolioPositions();
  const allocations = usePortfolioAllocations();
  const navigate = useNavigate();

  return (
    <PageContainer>
      <div className="flex items-start justify-between mb-6">
        <SectionHeader
          title="Portfolio"
          description="ETF & crypto positions powered by Tsumi"
        />
        {online && <ConnectInvestmentButton variant="outline" />}
      </div>

      {!online ? (
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-sm font-medium text-[var(--color-text-primary)]">Tsumi status</span>
              <Badge variant="warning">Offline</Badge>
            </div>
            <p className="text-sm text-[var(--color-text-muted)]">
              {DEPLOYMENT_MODE === 'selfhost' ? (
                <>
                  Tsumi is not reachable. Start it at{' '}
                  <code className="rounded bg-[var(--color-bg-elevated)] px-1 text-xs">
                    {import.meta.env.VITE_TSUMI_API_URL ?? 'http://localhost:8050'}
                  </code>{' '}
                  to see your portfolio here.
                </>
              ) : (
                'Portfolio data is temporarily unavailable. Please try again in a moment.'
              )}
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
          action={<ConnectInvestmentButton />}
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 mb-6">
            <KpiCard
              label="Totale"
              value={formatCurrency(summary.data?.totalValueEur ?? 0)}
            />
            <KpiCard
              label="P&L"
              value={formatCurrency(summary.data?.pnlEur ?? 0)}
              delta={summary.data?.pnlEur}
              deltaPct={summary.data?.pnlPct}
            />
            <KpiCard
              label="Positions"
              value={String(summary.data?.positionCount ?? positions.data.length)}
            />
          </div>

          {allocations.data && (
            <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
              <AllocationTable title="By asset class" groups={allocations.data.byAssetClass} />
              <AllocationTable title="By broker" groups={allocations.data.byBroker} />
              <AllocationTable title="By currency" groups={allocations.data.byCurrency} />
            </div>
          )}

          <SectionHeader title="Positions" className="mb-3" />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {positions.data.map((p) => (
              <button
                key={`${p.source}-${p.isin}`}
                type="button"
                onClick={() => navigate(`/portfolio/${p.source}/${p.isin}`)}
                className="text-left"
              >
                <KpiCard
                  label={`${p.name} (${p.isin})`}
                  value={formatCurrency(p.valueEur, p.currency)}
                  delta={p.pnlEur}
                  deltaPct={p.pnlPct}
                  subtitle={`${p.quantity} · ${p.source}`}
                />
              </button>
            ))}
          </div>
        </>
      )}
    </PageContainer>
  );
}
