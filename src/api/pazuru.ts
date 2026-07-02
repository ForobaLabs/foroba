import { fetchJson } from './fetchJson';

const BASE = import.meta.env.VITE_PAZURU_API_URL ?? '/pazuru-api';

export interface PazuruHealth {
  status: 'ok' | 'error' | 'unavailable';
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

// Deliberately soft/never-throwing: a health probe's "unavailable" result
// IS its valid outcome, not a failure to distinguish from loading/error.
async function safeFetch<T>(url: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return fallback;
    return (await res.json()) as T;
  } catch {
    return fallback;
  }
}

export async function fetchPazuruHealth(): Promise<PazuruHealth> {
  return safeFetch(`${BASE}/health`, { status: 'unavailable' as const });
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
