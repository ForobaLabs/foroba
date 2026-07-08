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
import { useNavigate, useParams } from 'react-router-dom';
import { useAccountDetail, useAccountTransactions } from '../hooks/useServiceHealth';

const BANK_LABELS: Record<string, string> = {
  revolut: 'Revolut',
  bnl: 'BNL',
  boursorama: 'Boursorama',
  hype: 'Hype',
};

function formatCurrency(amount: number, currency: string) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
}

export function AccountDetailPage() {
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
        Back to accounts
      </Button>

      {detail.isLoading ? (
        <LoadingState message="Loading account…" />
      ) : detail.isError || !detail.data ? (
        <ErrorState
          message="Could not load this account from Pazuru."
          onRetry={() => detail.refetch()}
        />
      ) : (
        <>
          <SectionHeader
            title={`${BANK_LABELS[detail.data.bankName] ?? detail.data.bankName} — ${detail.data.displayName}`}
            description="Account detail powered by Pazuru"
            className="mb-6"
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
            <KpiCard
              label="Balance"
              value={formatCurrency(detail.data.balance, detail.data.currency)}
            />
            <KpiCard
              label="Income this month"
              value={
                latestMonth
                  ? formatCurrency(latestMonth.incomeCents / 100, detail.data.currency)
                  : formatCurrency(0, detail.data.currency)
              }
            />
            <KpiCard
              label="Expense this month"
              value={
                latestMonth
                  ? formatCurrency(latestMonth.expenseCents / 100, detail.data.currency)
                  : formatCurrency(0, detail.data.currency)
              }
            />
            <KpiCard
              label="Savings this month"
              value={
                latestMonth
                  ? formatCurrency(latestMonth.savingsCents / 100, detail.data.currency)
                  : formatCurrency(0, detail.data.currency)
              }
            />
          </div>

          <SectionHeader title="Recent transactions" className="mb-3" />
          {transactions.isLoading ? (
            <LoadingState message="Loading transactions…" />
          ) : transactions.isError ? (
            <ErrorState
              message="Could not load transactions for this account."
              onRetry={() => transactions.refetch()}
            />
          ) : !transactions.data || transactions.data.length === 0 ? (
            <EmptyState title="No transactions" message="This account has no transactions yet." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Merchant</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions.data.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell>{t.bookedDate}</TableCell>
                    <TableCell>{t.merchant}</TableCell>
                    <TableCell>{t.category ?? 'other'}</TableCell>
                    <TableCell
                      className={`text-right ${t.amount < 0 ? 'text-[var(--color-negative)]' : 'text-[var(--color-positive)]'}`}
                    >
                      {formatCurrency(t.amount, t.currency)}
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
