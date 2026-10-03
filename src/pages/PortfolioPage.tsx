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
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import type { PortfolioAllocationGroup } from '../api/tsumi';
import {
  usePortfolioAllocations,
  usePortfolioPositions,
  usePortfolioSummary,
  useTsumiHealth,
} from '../hooks/useServiceHealth';

function ConnectInvestmentButton({ variant }: { variant?: 'outline' }) {
  const { t } = useTranslation();
  return (
    <a href="/foroba-api/auth/handoff/tsumi?redirect=/settings">
      <Button variant={variant} className="min-h-11">{t('data.portfolio.connect')}</Button>
    </a>
  );
}

function formatCurrency(amount: number, currency = 'EUR', lang = 'en') {
  return new Intl.NumberFormat(lang, { style: 'currency', currency }).format(amount);
}

function AllocationTable({ title, groups }: { title: string; groups: PortfolioAllocationGroup[] }) {
  const { t, i18n } = useTranslation();
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-[var(--color-text-primary)]">{title}</p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('data.portfolio.label')}</TableHead>
            <TableHead className="text-right">{t('data.portfolio.value')}</TableHead>
            <TableHead className="text-right">%</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {groups.map((g) => (
            <TableRow key={g.label}>
              <TableCell>{g.label}</TableCell>
              <TableCell className="text-right">{formatCurrency(g.valueEur, 'EUR', i18n.language)}</TableCell>
              <TableCell className="text-right">{g.pct.toFixed(1)}%</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function PortfolioPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
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
          as="h1"
          title={t('data.portfolio.title')}
          description={t('data.portfolio.description')}
        />
        {online && <ConnectInvestmentButton variant="outline" />}
      </div>

      {health.isLoading ? (
        // pazuru#149 (PROD-PZR-D03): `online` is false during the initial health
        // check too (data is undefined), so without this branch the page would
        // flash the "Offline" card before the check has actually resolved.
        <LoadingState message={t('data.portfolio.checking')} />
      ) : !online ? (
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-sm font-medium text-[var(--color-text-primary)]">{t('data.portfolio.status')}</span>
              <Badge variant="warning">{t('data.common.offline')}</Badge>
            </div>
            <p className="text-sm text-[var(--color-text-muted)]">
              {t('data.portfolio.unreachable')}
            </p>
          </CardContent>
        </Card>
      ) : positions.isLoading ? (
        <LoadingState message={t('data.portfolio.loading')} />
      ) : positions.isError ? (
        <ErrorState
          message={t('data.portfolio.error')}
          onRetry={() => positions.refetch()}
        />
      ) : !positions.data || positions.data.length === 0 ? (
        <EmptyState
          title={t('data.portfolio.emptyTitle')}
          message={t('data.portfolio.emptyBody')}
          action={<ConnectInvestmentButton />}
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 mb-6">
            <KpiCard
              label={t('data.common.total')}
              value={formatCurrency(summary.data?.totalValueEur ?? 0, 'EUR', lang)}
            />
            <KpiCard
              label={t('data.portfolio.pnl')}
              value={formatCurrency(summary.data?.pnlEur ?? 0, 'EUR', lang)}
              delta={summary.data?.pnlEur}
              deltaPct={summary.data?.pnlPct}
            />
            <KpiCard
              label={t('data.portfolio.positions')}
              value={String(summary.data?.positionCount ?? positions.data.length)}
            />
          </div>

          {allocations.data && (
            <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
              <AllocationTable title={t('data.portfolio.byAssetClass')} groups={allocations.data.byAssetClass} />
              <AllocationTable title={t('data.portfolio.byBroker')} groups={allocations.data.byBroker} />
              <AllocationTable title={t('data.portfolio.byCurrency')} groups={allocations.data.byCurrency} />
            </div>
          )}

          <SectionHeader title={t('data.portfolio.positions')} className="mb-3" />
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
                  value={formatCurrency(p.valueEur, p.currency, lang)}
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
