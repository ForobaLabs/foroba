import type { NetWorthSnapshot } from '@foroba/ui';
import { fetchJson } from './fetchJson';
import { fetchDetailedHealthBody, fetchHealthBody } from './health';
import type { DetailedHealth } from './health';

export type { DependencyStatus, DetailedHealth } from './health';

export interface ForobaHealth {
  status: 'ok' | 'degraded' | 'unavailable';
  checks?: { db: 'ok' | 'down' };
}

const FOROBA_BASE = '/foroba-api';

export async function fetchForobaHealth(): Promise<ForobaHealth> {
  return fetchHealthBody(`${FOROBA_BASE}/health`, { status: 'unavailable' as const });
}

export async function fetchForobaHealthDetailed(): Promise<DetailedHealth> {
  return fetchDetailedHealthBody(`${FOROBA_BASE}/health/detailed`, {
    status: 'unavailable' as const,
    dependencies: {},
  });
}

export type NetWorthSource = 'pazuru' | 'tsumi';

export interface NetWorthHistoryPoint {
  date: string;
  totalEur: number;
}

export interface NetWorthResult {
  /** Best-effort aggregated snapshot (latest point). Failed sources contribute 0. */
  snapshot: NetWorthSnapshot;
  /** Daily bank+investments history — real series, not a single point (foroba#157). */
  history: NetWorthHistoryPoint[];
  /** Sources that failed to load for this fetch. Empty = fully healthy. */
  degradedSources: NetWorthSource[];
}

interface NetWorthApiResponse {
  bank: { total_cents: number; currency: string; account_count: number } | null;
  investments: { total_eur: number; pnl_eur: number; pnl_pct: number; position_count: number } | null;
  total_eur: number;
  history: Array<{ date: string; bank_eur: number; investments_eur: number; total_eur: number }>;
  degraded: boolean;
  disclaimer: string;
}

/**
 * Aggregates Pazuru (cash) + Tsumi (portfolio) into a unified net worth
 * snapshot + real daily history, via Foroba's own `/networth/summary`
 * backend endpoint (server-side fan-out, see networth_service.py). The
 * backend already degrades gracefully (never 500s) when either sub-app
 * is down — failed sections come back `null` and `degraded: true` — so
 * this function just maps that response onto the UI's `NetWorthResult`
 * shape and translates `bank`/`investments` nulls into `degradedSources`.
 */
export async function fetchNetWorth(days = 365): Promise<NetWorthResult> {
  const res = await fetchJson<NetWorthApiResponse>(
    `/foroba-api/networth/summary?days=${days}`,
    { credentials: 'include', timeoutMs: 8000 },
  );

  const degradedSources: NetWorthSource[] = [];
  if (res.bank === null) degradedSources.push('pazuru');
  if (res.investments === null) degradedSources.push('tsumi');

  const cashEur = res.bank ? res.bank.total_cents / 100 : 0;
  const portfolioEur = res.investments ? res.investments.total_eur : 0;
  const last = res.history[res.history.length - 1];
  const prev = res.history[res.history.length - 2];
  const delta1d = last && prev ? last.total_eur - prev.total_eur : undefined;
  const delta1dPct = delta1d !== undefined && prev && prev.total_eur !== 0
    ? (delta1d / prev.total_eur) * 100
    : undefined;

  return {
    snapshot: {
      date: last?.date ?? new Date().toISOString(),
      totalEur: res.total_eur,
      cashEur,
      portfolioEur,
      delta1d,
      delta1dPct,
    },
    history: res.history.map((p) => ({ date: p.date, totalEur: p.total_eur })),
    degradedSources,
  };
}
