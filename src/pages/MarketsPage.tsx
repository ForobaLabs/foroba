import { Badge, Card, CardContent, EmptyState, ErrorState, LoadingState, PageContainer, SectionHeader } from '@foroba/ui';
import { useState } from 'react';
import { useMarketSnapshot } from '../hooks/useMarketSnapshot';
import type { AssetClass } from '../api/markets';

const SYMBOLS: Record<AssetClass, string[]> = {
  crypto: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
  equity: ['AAPL.US', 'MSFT.US', 'NVDA.US'],
};

export function MarketsPage() {
  const [assetClass, setAssetClass] = useState<AssetClass>('crypto');
  const [symbol, setSymbol] = useState<string>('BTCUSDT');
  const { data, isLoading, isError, refetch } = useMarketSnapshot(symbol, assetClass);

  return (
    <PageContainer>
      <SectionHeader
        title="Markets"
        description="A cross-app market snapshot aggregated from Tsumi analysis"
        className="mb-6"
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <select
          aria-label="Asset class"
          value={assetClass}
          onChange={(e) => {
            const next = e.target.value as AssetClass;
            setAssetClass(next);
            setSymbol(SYMBOLS[next][0]);
          }}
          className="rounded border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-sm"
        >
          <option value="crypto">Crypto</option>
          <option value="equity">Equity</option>
        </select>
        <select
          aria-label="Symbol"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          className="rounded border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-sm"
        >
          {SYMBOLS[assetClass].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

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
