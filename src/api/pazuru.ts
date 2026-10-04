import { fetchJson } from './fetchJson';
import { fetchDetailedHealthBody, fetchHealthBody } from './health';
import type { DetailedHealth } from './health';

const BASE = import.meta.env.VITE_PAZURU_API_URL ?? '/pazuru-api';

export interface PazuruHealth {
  status: 'ok' | 'degraded' | 'error' | 'unavailable';
  checks?: { db: 'ok' | 'down' };
}

export interface PazuruSummary {
  totalBalance: number;
  currency: string;
}

export interface PazuruAccount {
  id: number;
  bankName: string;
  displayName: string;
  currency: string;
  balance: number;
}

export async function fetchPazuruHealth(): Promise<PazuruHealth> {
  return fetchHealthBody(`${BASE}/health`, { status: 'unavailable' as const });
}

export async function fetchPazuruHealthDetailed(): Promise<DetailedHealth> {
  return fetchDetailedHealthBody(`${BASE}/health/detailed`, {
    status: 'unavailable' as const,
    dependencies: {},
  });
}

export async function fetchPazuruSummary(): Promise<PazuruSummary> {
  const data = await fetchJson<{ total_balance_cents: number }>(
    `${BASE}/api/analytics/summary`,
    { timeoutMs: 5000 },
  );
  return { totalBalance: (data.total_balance_cents ?? 0) / 100, currency: 'EUR' };
}

interface RawPazuruAccount {
  id: number;
  bank_name: string;
  display_name: string;
  currency: string;
  balance_cents: number;
}

export async function fetchPazuruAccounts(): Promise<PazuruAccount[]> {
  const data = await fetchJson<RawPazuruAccount[]>(`${BASE}/api/accounts`, {
    credentials: 'include',
    timeoutMs: 5000,
  });
  return data.map((a) => ({
    id: a.id,
    bankName: a.bank_name,
    displayName: a.display_name,
    currency: a.currency,
    balance: a.balance_cents / 100,
  }));
}

export interface PazuruAccountMonth {
  month: string;
  incomeCents: number;
  expenseCents: number;
  savingsCents: number;
}

export interface PazuruAccountDetail extends PazuruAccount {
  monthlyTrend: PazuruAccountMonth[];
}

interface RawPazuruAccountDetail extends RawPazuruAccount {
  monthly_trend: { month: string; income_cents: number; expense_cents: number; savings_cents: number }[];
}

export async function fetchPazuruAccountDetail(accountId: number): Promise<PazuruAccountDetail> {
  const data = await fetchJson<RawPazuruAccountDetail>(`${BASE}/api/accounts/${accountId}`, {
    credentials: 'include',
    timeoutMs: 5000,
  });
  return {
    id: data.id,
    bankName: data.bank_name,
    displayName: data.display_name,
    currency: data.currency,
    balance: data.balance_cents / 100,
    monthlyTrend: data.monthly_trend.map((m) => ({
      month: m.month,
      incomeCents: m.income_cents,
      expenseCents: m.expense_cents,
      savingsCents: m.savings_cents,
    })),
  };
}

export interface PazuruTransaction {
  id: number;
  bookedDate: string;
  amount: number;
  currency: string;
  merchant: string;
  category: string | null;
}

interface RawPazuruTransactionsPage {
  items: {
    id: number;
    booked_date: string;
    amount_cents: number;
    currency: string;
    raw_label: string;
    normalized_merchant: string | null;
    category: string | null;
  }[];
}

export async function fetchPazuruAccountTransactions(
  accountId: number,
): Promise<PazuruTransaction[]> {
  const data = await fetchJson<RawPazuruTransactionsPage>(
    `${BASE}/api/transactions?account_id=${accountId}&page_size=25`,
    { credentials: 'include', timeoutMs: 5000 },
  );
  return data.items.map((t) => ({
    id: t.id,
    bookedDate: t.booked_date,
    amount: t.amount_cents / 100,
    currency: t.currency,
    merchant: t.normalized_merchant ?? t.raw_label,
    category: t.category,
  }));
}

export interface PazuruGoal {
  id: number;
  name: string;
  targetCents: number;
  savedCents: number;
  monthlyContributionCents: number;
  deadline: string | null;
}

interface RawPazuruGoal {
  id: number;
  name: string;
  target_cents: number;
  saved_cents: number;
  monthly_contribution_cents: number;
  deadline: string | null;
}

export async function fetchPazuruGoals(): Promise<PazuruGoal[]> {
  const data = await fetchJson<RawPazuruGoal[]>(`${BASE}/api/goals`, {
    credentials: 'include',
    timeoutMs: 5000,
  });
  return data.map((g) => ({
    id: g.id,
    name: g.name,
    targetCents: g.target_cents,
    savedCents: g.saved_cents,
    monthlyContributionCents: g.monthly_contribution_cents,
    deadline: g.deadline,
  }));
}

/** Downloads the transactions export through fetch so a failure can be surfaced
 * (a plain navigation to a failing URL replaces the page with raw JSON). */
export async function downloadPazuruTransactions(format: 'xlsx' | 'csv'): Promise<void> {
  const res = await fetch(`${BASE}/api/export/transactions?format=${format}`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`export failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `transactions.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
