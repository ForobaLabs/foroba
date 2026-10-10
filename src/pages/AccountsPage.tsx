import { Badge, Button, Card, CardContent, EmptyState, ErrorState, ExportButton, KpiCard, LoadingState, PageContainer, SectionHeader, formatCurrency, formatNumber } from '@foroba/ui';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { downloadPazuruTransactions } from '../api/pazuru';
import { useAccountsList, usePazuruHealth } from '../hooks/useServiceHealth';

const BANK_LABELS: Record<string, string> = {
  revolut: 'Revolut',
  bnl: 'BNL',
  boursorama: 'Boursorama',
  hype: 'Hype',
};

function ConnectBankButton({ variant }: { variant?: 'outline' }) {
  const { t } = useTranslation();
  return (
    <a href="/foroba-api/auth/handoff/pazuru?redirect=/settings">
      <Button variant={variant} className="min-h-11">{t('data.accounts.connect')}</Button>
    </a>
  );
}

export function AccountsPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const health = usePazuruHealth();
  const online = health.data?.status === 'ok';
  const accounts = useAccountsList();
  const navigate = useNavigate();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(false);

  const runExport = async (fmt: 'xlsx' | 'csv') => {
    setExporting(true);
    setExportError(false);
    try {
      await downloadPazuruTransactions(fmt);
    } catch {
      setExportError(true);
    } finally {
      setExporting(false);
    }
  };

  return (
    <PageContainer>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <SectionHeader
          as="h1"
          title={t('data.accounts.title')}
          description={t('data.accounts.description')}
        />
        {online && (accounts.data?.length ?? 0) > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <ConnectBankButton variant="outline" />
            <ExportButton loading={exporting} onExport={runExport} />
          </div>
        )}
      </div>

      {exportError && (
        <p role="alert" className="mb-4 text-sm text-[var(--color-negative)]">
          {t('data.accounts.exportFailed')}
        </p>
      )}

      {health.isLoading ? (
        // pazuru#149 (PROD-PZR-D03): `online` is false during the initial health
        // check too (data is undefined), so without this branch the page would
        // flash the "Offline" card before the check has actually resolved.
        <LoadingState message={t('data.accounts.checking')} />
      ) : !online ? (
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-sm font-medium text-[var(--color-text-primary)]">{t('data.accounts.status')}</span>
              <Badge variant="warning">{t('data.common.offline')}</Badge>
            </div>
            <p className="text-sm text-[var(--color-text-muted)]">{t('data.accounts.unreachable')}</p>
          </CardContent>
        </Card>
      ) : accounts.isLoading ? (
        <LoadingState message={t('data.accounts.loading')} />
      ) : accounts.isError ? (
        <ErrorState
          message={t('data.accounts.error')}
          onRetry={() => accounts.refetch()}
        />
      ) : !accounts.data || accounts.data.length === 0 ? (
        <EmptyState
          title={t('data.accounts.emptyTitle')}
          message={t('data.accounts.emptyBody')}
          action={<ConnectBankButton />}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <KpiCard
            label={t('data.common.total')}
            value={
              new Set(accounts.data.map((a) => a.currency)).size === 1
                ? formatCurrency(
                    accounts.data.reduce((sum, a) => sum + a.balance, 0),
                    accounts.data[0].currency,
                    lang,
                  )
                : formatNumber(accounts.data.reduce((sum, a) => sum + a.balance, 0), lang, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })
            }
            subtitle={
              new Set(accounts.data.map((a) => a.currency)).size === 1
                ? undefined
                : t('data.accounts.mixed')
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
                value={formatCurrency(acc.balance, acc.currency, lang)}
              />
            </button>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
