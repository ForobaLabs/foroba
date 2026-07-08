import {
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  LoadingState,
  PageContainer,
  SectionHeader,
} from '@foroba/ui';
import { ArrowLeft } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import type { AssetClass } from '../api/markets';
import { useMarketSnapshot } from '../hooks/useMarketSnapshot';

export function MarketDetailPage() {
  const { assetClass, symbol } = useParams<{ assetClass: AssetClass; symbol: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useMarketSnapshot(
    symbol ?? '',
    (assetClass as AssetClass) ?? 'crypto',
  );

  return (
    <PageContainer>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/markets')}
        className="mb-4 inline-flex items-center gap-1.5"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to markets
      </Button>

      <SectionHeader
        title={symbol ?? 'Asset'}
        description={`${assetClass} · rating, sentiment & movers powered by Tsumi`}
        className="mb-6"
      />

      <Card>
        <CardContent className="p-6">
          {isLoading && <LoadingState message="Loading snapshot…" />}

          {!isLoading && isError && (
            <ErrorState
              message="Market data is currently unavailable. Make sure Tsumi is running."
              onRetry={() => refetch()}
            />
          )}

          {!isLoading && !isError && !data && (
            <EmptyState message="No market data available for this symbol yet." />
          )}

          {!isLoading && !isError && data && (
            <div className="space-y-4">
              {data.degraded && (
                <Badge variant="warning">Partial data — some sections offline</Badge>
              )}

              <div>
                <h3 className="mb-1 text-sm font-medium text-[var(--color-text-primary)]">
                  {data.symbol} · rating
                </h3>
                {data.rating ? (
                  <Badge variant="positive">
                    {data.rating.label} ({data.rating.score.toFixed(2)})
                  </Badge>
                ) : (
                  <span className="text-sm text-[var(--color-text-muted)]">Unavailable</span>
                )}
              </div>

              <div>
                <h3 className="mb-1 text-sm font-medium text-[var(--color-text-primary)]">
                  Sentiment
                </h3>
                <span className="text-sm text-[var(--color-text-secondary)]">
                  {data.sentiment
                    ? `${data.sentiment.sentiment.label} (${data.sentiment.sentiment.score.toFixed(2)})`
                    : 'Unavailable'}
                </span>
              </div>

              <div>
                <h3 className="mb-1 text-sm font-medium text-[var(--color-text-primary)]">
                  Top movers
                </h3>
                {data.movers && data.movers.length > 0 ? (
                  <ul className="space-y-1">
                    {data.movers.map((m) => (
                      <li
                        key={m.symbol}
                        className="flex justify-between text-sm text-[var(--color-text-secondary)]"
                      >
                        <span>{m.symbol}</span>
                        <span>{m.change_pct.toFixed(2)}%</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-sm text-[var(--color-text-muted)]">Unavailable</span>
                )}
              </div>

              <p className="pt-2 text-xs text-[var(--color-text-muted)]">{data.disclaimer}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </PageContainer>
  );
}
