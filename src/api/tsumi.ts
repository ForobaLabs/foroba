import { fetchJson } from './fetchJson';

const BASE = import.meta.env.VITE_TSUMI_API_URL ?? '/tsumi-api';

export interface TsumiHealth {
  status: 'ok' | 'error' | 'unavailable';
}

export interface TsumiSummary {
  totalValueEur: number;
  pnlEur: number;
  pnlPct: number;
  positionCount: number;
}

export interface PortfolioPosition {
  id: number | null;
  isin: string;
  name: string;
  assetClass: string;
  currency: string;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  purchaseDate: string | null;
  accountType: string;
  valueEur: number;
  pnlEur: number;
  pnlPct: number;
  source: string;
}

export interface PortfolioAllocationGroup {
  label: string;
  valueEur: number;
  pct: number;
}

export interface PortfolioAllocations {
  byAssetClass: PortfolioAllocationGroup[];
  byBroker: PortfolioAllocationGroup[];
  byCurrency: PortfolioAllocationGroup[];
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
  const data = await fetchJson<{
    total_eur: number;
    pnl_eur: number;
    pnl_pct: number;
    position_count: number;
  }>(`${BASE}/api/portfolio/summary`, { timeoutMs: 5000 });
  return {
    totalValueEur: data.total_eur ?? 0,
    pnlEur: data.pnl_eur ?? 0,
    pnlPct: data.pnl_pct ?? 0,
    positionCount: data.position_count ?? 0,
  };
}

interface RawPosition {
  id: number | null;
  isin: string;
  name: string;
  asset_class: string;
  currency: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  purchase_date: string | null;
  account_type: string;
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
    avgCost: p.avg_cost,
    currentPrice: p.current_price,
    purchaseDate: p.purchase_date,
    accountType: p.account_type,
    valueEur: p.value_eur,
    pnlEur: p.pnl_eur,
    pnlPct: p.pnl_pct,
    source: p.source,
  }));
}

interface RawAllocationGroup {
  label: string;
  value_eur: number;
  pct: number;
}

export async function fetchPortfolioAllocations(): Promise<PortfolioAllocations> {
  const data = await fetchJson<{
    by_asset_class: RawAllocationGroup[];
    by_broker: RawAllocationGroup[];
    by_currency: RawAllocationGroup[];
  }>(`${BASE}/api/portfolio/allocations`, { credentials: 'include', timeoutMs: 5000 });
  const map = (g: RawAllocationGroup[]): PortfolioAllocationGroup[] =>
    g.map((x) => ({ label: x.label, valueEur: x.value_eur, pct: x.pct }));
  return {
    byAssetClass: map(data.by_asset_class),
    byBroker: map(data.by_broker),
    byCurrency: map(data.by_currency),
  };
}
