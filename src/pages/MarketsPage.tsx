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
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-[var(--color-text-primary)]">{title}</p>
      {!movers ? (
        <p className="text-sm text-[var(--color-text-muted)]">{t('data.common.unavailable')}</p>
      ) : movers.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)]">{t('data.markets.noMovers')}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('data.markets.symbol')}</TableHead>
              <TableHead className="text-right">{t('data.markets.change')}</TableHead>
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
  const { t, i18n } = useTranslation();
  const [assetClass, setAssetClass] = useState<AssetClass>('crypto');
  const { data, isLoading, isError, refetch } = useMarketOverview(assetClass);
  const navigate = useNavigate();

  const goToDetail = (symbol: string) => navigate(`/markets/${assetClass}/${symbol}`);

  return (
    <PageContainer>
      <SectionHeader
        title={t('data.markets.title')}
        description={t('data.markets.description')}
        className="mb-6"
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <select
          aria-label={t('data.markets.assetClass')}
          value={assetClass}
          onChange={(e) => setAssetClass(e.target.value as AssetClass)}
          className="min-h-11 rounded border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 text-base"
        >
          <option value="crypto">{t('data.markets.crypto')}</option>
          <option value="equity">{t('data.markets.equity')}</option>
          <option value="etf">{t('data.markets.etf')}</option>
          <option value="bond">{t('data.markets.bond')}</option>
        </select>
      </div>

      {isLoading ? (
        <LoadingState message={t('data.markets.loading')} />
      ) : isError ? (
        <ErrorState
          message={t('data.markets.error')}
          onRetry={() => refetch()}
        />
      ) : !data ? (
        <EmptyState message={t('data.markets.empty')} />
      ) : (
        <div className="space-y-6">
          {data.degraded && (
            <Badge variant="warning">{t('data.common.partial')}</Badge>
          )}

          <Card>
            <CardContent className="p-6">
              <p className="mb-3 text-sm font-medium text-[var(--color-text-primary)]">
                {t('data.markets.news')}
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
                      <span className="ml-2 text-xs text-[var(--color-text-muted)] tabular-nums">
                        {item.source}
                        {item.published && !Number.isNaN(Date.parse(item.published)) && (
                          <> · {new Intl.DateTimeFormat(i18n.language, { day: 'numeric', month: 'short' }).format(new Date(item.published))}</>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)]">{t('data.common.unavailable')}</p>
              )}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardContent className="p-6">
                <MoversTable title={t('data.markets.gainers')} movers={data.gainers} onSelect={goToDetail} />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <MoversTable title={t('data.markets.losers')} movers={data.losers} onSelect={goToDetail} />
              </CardContent>
            </Card>
          </div>

          <p className="text-xs text-[var(--color-text-muted)]">{data.disclaimer}</p>
        </div>
      )}
    </PageContainer>
  );
}
