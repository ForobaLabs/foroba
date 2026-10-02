import {
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  ExportButton,
  KpiCard,
  LoadingState,
  PageContainer,
  SectionHeader,
} from '@foroba/ui';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
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

  return (
    <PageContainer>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <SectionHeader
          title={t('data.accounts.title')}
          description={t('data.accounts.description')}
        />
        {online && (
          <div className="flex flex-wrap items-center gap-2">
            <ConnectBankButton variant="outline" />
            <ExportButton onExport={(fmt) => { window.location.href = `/pazuru-api/export/transactions?format=${fmt}`; }} />
          </div>
        )}
      </div>

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
                ? new Intl.NumberFormat(lang, {
                    style: 'currency',
                    currency: accounts.data[0].currency,
                  }).format(accounts.data.reduce((sum, a) => sum + a.balance, 0))
                : accounts.data.reduce((sum, a) => sum + a.balance, 0).toFixed(2)
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
                value={new Intl.NumberFormat(lang, {
                  style: 'currency',
                  currency: acc.currency,
                }).format(acc.balance)}
              />
            </button>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
