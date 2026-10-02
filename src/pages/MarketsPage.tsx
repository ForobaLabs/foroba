import {
  Badge,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
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
import { useState } from 'react';
import { useNavigate } from 'react-router';
import type { AssetClass, MarketMover } from '../api/markets';
import { useMarketOverview } from '../hooks/useMarketSnapshot';

function MoversTable({
  title,
  movers,
  onSelect,
}: {
  title: string;
  movers: MarketMover[] | null;
  onSelect: (symbol: string) => void;
}) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-[var(--color-text-primary)]">{title}</p>
      {!movers || movers.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)]">Unavailable</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Symbol</TableHead>
              <TableHead className="text-right">Change</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {movers.map((m) => (
              <TableRow key={m.symbol}>
                <TableCell>
                  <button
                    type="button"
                    onClick={() => onSelect(m.symbol)}
                    className="text-left text-[var(--color-accent)] hover:underline"
                  >
                    {m.symbol}
                  </button>
                </TableCell>
                <TableCell
                  className={`text-right ${m.change_pct >= 0 ? 'text-[var(--color-positive)]' : 'text-[var(--color-negative)]'}`}
                >
                  {m.change_pct >= 0 ? '+' : ''}
                  {m.change_pct.toFixed(2)}%
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

export function MarketsPage() {
  const [assetClass, setAssetClass] = useState<AssetClass>('crypto');
  const { data, isLoading, isError, refetch } = useMarketOverview(assetClass);
  const navigate = useNavigate();

  const goToDetail = (symbol: string) => navigate(`/markets/${assetClass}/${symbol}`);

  return (
    <PageContainer>
      <SectionHeader
        title="Markets"
        description="Market news, top movers, and asset detail — powered by Yiriba"
        className="mb-6"
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <select
          aria-label="Asset class"
          value={assetClass}
          onChange={(e) => setAssetClass(e.target.value as AssetClass)}
          className="rounded border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-sm"
        >
          <option value="crypto">Crypto</option>
          <option value="equity">Equity</option>
          <option value="etf">ETF</option>
          <option value="bond">Bond</option>
        </select>
      </div>

      {isLoading ? (
        <LoadingState message="Loading markets…" />
      ) : isError ? (
        <ErrorState
          message="Market data is currently unavailable. Make sure Yiriba is running."
          onRetry={() => refetch()}
        />
      ) : !data ? (
        <EmptyState message="No market data available yet." />
      ) : (
        <div className="space-y-6">
          {data.degraded && (
            <Badge variant="warning">Partial data — some sections offline</Badge>
          )}

          <Card>
            <CardContent className="p-6">
              <p className="mb-3 text-sm font-medium text-[var(--color-text-primary)]">
                Market news
              </p>
              {data.news && data.news.items.length > 0 ? (
                <ul className="space-y-2">
                  {data.news.items.map((item) => (
                    <li key={item.title} className="text-sm">
                      <a
                        href={item.link}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[var(--color-text-primary)] hover:underline"
                      >
                        {item.title}
                      </a>
                      <span className="ml-2 text-xs text-[var(--color-text-muted)]">
                        {item.source}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)]">Unavailable</p>
              )}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardContent className="p-6">
                <MoversTable title="Top gainers" movers={data.gainers} onSelect={goToDetail} />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <MoversTable title="Top losers" movers={data.losers} onSelect={goToDetail} />
              </CardContent>
            </Card>
          </div>

          <p className="text-xs text-[var(--color-text-muted)]">{data.disclaimer}</p>
        </div>
      )}
    </PageContainer>
  );
}
