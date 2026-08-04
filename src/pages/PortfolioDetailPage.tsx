import {
  Button,
  ErrorState,
  KpiCard,
  LoadingState,
  PageContainer,
  SectionHeader,
} from '@foroba/ui';
import { ArrowLeft } from 'lucide-react';
import { useNavigate, useParams } from 'react-router';
import { usePortfolioPositions } from '../hooks/useServiceHealth';

function formatCurrency(amount: number, currency: string) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
}

export function PortfolioDetailPage() {
  const { source, isin } = useParams<{ source: string; isin: string }>();
  const navigate = useNavigate();
  const positions = usePortfolioPositions();

  const position = positions.data?.find((p) => p.source === source && p.isin === isin);

  return (
    <PageContainer>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/portfolio')}
        className="mb-4 inline-flex items-center gap-1.5"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to portfolio
      </Button>

      {positions.isLoading ? (
        <LoadingState message="Loading position…" />
      ) : positions.isError ? (
        <ErrorState
          message="Could not load this position from Tsumi."
          onRetry={() => positions.refetch()}
        />
      ) : !position ? (
        <ErrorState message="Position not found." />
      ) : (
        <>
          <SectionHeader
            title={`${position.name} (${position.isin})`}
            description={`${position.assetClass} · ${position.source}`}
            className="mb-6"
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
            <KpiCard
              label="Value"
              value={formatCurrency(position.valueEur, position.currency)}
              delta={position.pnlEur}
              deltaPct={position.pnlPct}
            />
            <KpiCard label="Quantity" value={String(position.quantity)} />
            <KpiCard
              label="Avg cost"
              value={formatCurrency(position.avgCost, position.currency)}
            />
            <KpiCard
              label="Current price"
              value={formatCurrency(position.currentPrice, position.currency)}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <KpiCard label="Account type" value={position.accountType} />
            <KpiCard label="Purchase date" value={position.purchaseDate ?? '—'} />
            <KpiCard label="Currency" value={position.currency} />
          </div>
        </>
      )}
    </PageContainer>
  );
}
