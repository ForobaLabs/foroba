import { fetchJson } from './fetchJson';

const BASE = import.meta.env.VITE_TSUMI_API_URL ?? '/tsumi-api';

export interface TsumiHealth {
  status: 'ok' | 'error' | 'unavailable';
}

export interface TsumiSummary {
  totalValueEur: number;
}

export interface PortfolioPosition {
  id: number | null;
  isin: string;
  name: string;
  assetClass: string;
  currency: string;
  quantity: number;
  valueEur: number;
  pnlEur: number;
  pnlPct: number;
  source: string;
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

export async function fetchTsumiHealth(): Promise<TsumiHealth> {
  return safeFetch(`${BASE}/health`, { status: 'unavailable' as const });
}

export async function fetchTsumiSummary(): Promise<TsumiSummary> {
  const data = await fetchJson<{ total_eur: number }>(
    `${BASE}/api/portfolio/summary`,
    { timeoutMs: 5000 },
  );
  return { totalValueEur: data.total_eur ?? 0 };
}

interface RawPosition {
  id: number | null;
  isin: string;
  name: string;
  asset_class: string;
  currency: string;
  quantity: number;
  value_eur: number;
  pnl_eur: number;
  pnl_pct: number;
  source: string;
}

export async function fetchPortfolioPositions(): Promise<PortfolioPosition[]> {
  const data = await fetchJson<RawPosition[]>(`${BASE}/api/portfolio/positions`, {
    credentials: 'include',
    timeoutMs: 5000,
  });
  return data.map((p) => ({
    id: p.id,
    isin: p.isin,
    name: p.name,
    assetClass: p.asset_class,
    currency: p.currency,
    quantity: p.quantity,
    valueEur: p.value_eur,
    pnlEur: p.pnl_eur,
    pnlPct: p.pnl_pct,
    source: p.source,
  }));
}
