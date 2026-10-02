import {
  Button,
  ErrorState,
  KpiCard,
  LoadingState,
  PageContainer,
  SectionHeader,
} from '@foroba/ui';
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router';
import { usePortfolioPositions } from '../hooks/useServiceHealth';

function formatCurrency(amount: number, currency: string, lang: string) {
  return new Intl.NumberFormat(lang, { style: 'currency', currency }).format(amount);
}

export function PortfolioDetailPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
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
        {t('positionDetail.back')}
      </Button>

      {positions.isLoading ? (
        <LoadingState message={t('positionDetail.loading')} />
      ) : positions.isError ? (
        <ErrorState
          message={t('positionDetail.error')}
          onRetry={() => positions.refetch()}
        />
      ) : !position ? (
        <ErrorState message={t('positionDetail.notFound')} />
      ) : (
        <>
          <SectionHeader
            title={`${position.name} (${position.isin})`}
            description={`${position.assetClass} · ${position.source}`}
            className="mb-6"
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
            <KpiCard
              label={t('positionDetail.value')}
              value={formatCurrency(position.valueEur, position.currency, lang)}
              delta={position.pnlEur}
              deltaPct={position.pnlPct}
            />
            <KpiCard label={t('positionDetail.quantity')} value={String(position.quantity)} />
            <KpiCard
              label={t('positionDetail.avgCost')}
              value={formatCurrency(position.avgCost, position.currency, lang)}
            />
            <KpiCard
              label={t('positionDetail.currentPrice')}
              value={formatCurrency(position.currentPrice, position.currency, lang)}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <KpiCard label={t('positionDetail.accountType')} value={position.accountType} />
            <KpiCard label={t('positionDetail.purchaseDate')} value={position.purchaseDate ?? '—'} />
            <KpiCard label={t('positionDetail.currency')} value={position.currency} />
          </div>
        </>
      )}
    </PageContainer>
  );
}
