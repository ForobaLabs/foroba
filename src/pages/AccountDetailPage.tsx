import {
  Button,
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
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router';
import { useAccountDetail, useAccountTransactions } from '../hooks/useServiceHealth';

const BANK_LABELS: Record<string, string> = {
  revolut: 'Revolut',
  bnl: 'BNL',
  boursorama: 'Boursorama',
  hype: 'Hype',
};

function formatCurrency(amount: number, currency: string, lang: string) {
  return new Intl.NumberFormat(lang, { style: 'currency', currency }).format(amount);
}

export function AccountDetailPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const money = (amount: number, currency: string) => formatCurrency(amount, currency, lang);
  const { id } = useParams<{ id: string }>();
  const accountId = Number(id);
  const navigate = useNavigate();

  const detail = useAccountDetail(accountId);
  const transactions = useAccountTransactions(accountId);

  const latestMonth = detail.data?.monthlyTrend.at(-1);

  return (
    <PageContainer>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/accounts')}
        className="mb-4 inline-flex items-center gap-1.5"
      >
        <ArrowLeft className="h-4 w-4" />
        {t('data.accountDetail.back')}
      </Button>

      {detail.isLoading ? (
        <LoadingState message={t('data.accountDetail.loading')} />
      ) : detail.isError || !detail.data ? (
        <ErrorState
          message={t('data.accountDetail.error')}
          onRetry={() => detail.refetch()}
        />
      ) : (
        <>
          <SectionHeader
            as="h1"
            title={`${BANK_LABELS[detail.data.bankName] ?? detail.data.bankName} — ${detail.data.displayName}`}
            description={t('data.accountDetail.description')}
            className="mb-6"
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
            <KpiCard
              label={t('data.accountDetail.balance')}
              value={money(detail.data.balance, detail.data.currency)}
            />
            <KpiCard
              label={t('data.accountDetail.income')}
              value={
                latestMonth
                  ? money(latestMonth.incomeCents / 100, detail.data.currency)
                  : money(0, detail.data.currency)
              }
            />
            <KpiCard
              label={t('data.accountDetail.expense')}
              value={
                latestMonth
                  ? money(latestMonth.expenseCents / 100, detail.data.currency)
                  : money(0, detail.data.currency)
              }
            />
            <KpiCard
              label={t('data.accountDetail.savings')}
              value={
                latestMonth
                  ? money(latestMonth.savingsCents / 100, detail.data.currency)
                  : money(0, detail.data.currency)
              }
            />
          </div>

          <SectionHeader title={t('data.accountDetail.recent')} className="mb-3" />
          {transactions.isLoading ? (
            <LoadingState message={t('data.accountDetail.txLoading')} />
          ) : transactions.isError ? (
            <ErrorState
              message={t('data.accountDetail.txError')}
              onRetry={() => transactions.refetch()}
            />
          ) : !transactions.data || transactions.data.length === 0 ? (
            <EmptyState
              title={t('data.accountDetail.txEmptyTitle')}
              message={t('data.accountDetail.txEmptyBody')}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('data.accountDetail.date')}</TableHead>
                  <TableHead>{t('data.accountDetail.merchant')}</TableHead>
                  <TableHead>{t('data.accountDetail.category')}</TableHead>
                  <TableHead className="text-right">{t('data.accountDetail.amount')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions.data.map((tx) => (
                  <TableRow key={tx.id}>
                    <TableCell>{tx.bookedDate}</TableCell>
                    <TableCell>{tx.merchant}</TableCell>
                    <TableCell>{tx.category ?? t('data.accountDetail.other')}</TableCell>
                    <TableCell
                      className={`text-right ${tx.amount < 0 ? 'text-[var(--color-negative)]' : 'text-[var(--color-positive)]'}`}
                    >
                      {money(tx.amount, tx.currency)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
    </PageContainer>
  );
}
