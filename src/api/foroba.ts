import type { NetWorthSnapshot } from '@foroba/ui';
import { fetchDetailedHealthBody, fetchHealthBody } from './health';
import type { DetailedHealth } from './health';
import { fetchPazuruSummary } from './pazuru';
import { fetchTsumiSummary } from './tsumi';

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

export interface NetWorthResult {
  /** Best-effort aggregated snapshot. Failed sources contribute 0. */
  snapshot: NetWorthSnapshot;
  /** Sources that failed to load for this fetch. Empty = fully healthy. */
  degradedSources: NetWorthSource[];
}

/**
 * Aggregates Pazuru (cash) + Tsumi (portfolio) into a single net worth
 * snapshot. Uses `Promise.allSettled` (NOT `Promise.all`) so that one
 * sub-app being down never blocks the other's data — per foroba#126's
 * "nessun blocco permanente se una sotto-app è down" requirement. A
 * source that fails contributes 0 to its field and is reported in
 * `degradedSources`; this function itself only rejects if something
 * unexpected happens outside the two settled fetches.
 */
export async function fetchNetWorth(): Promise<NetWorthResult> {
  const [pazuruResult, tsumiResult] = await Promise.allSettled([
    fetchPazuruSummary(),
    fetchTsumiSummary(),
  ]);

  const degradedSources: NetWorthSource[] = [];

  let cashEur = 0;
  if (pazuruResult.status === 'fulfilled') {
    cashEur = pazuruResult.value.totalBalance;
  } else {
    degradedSources.push('pazuru');
  }

  let portfolioEur = 0;
  if (tsumiResult.status === 'fulfilled') {
    portfolioEur = tsumiResult.value.totalValueEur;
  } else {
    degradedSources.push('tsumi');
  }

  return {
    snapshot: {
      date: new Date().toISOString(),
      totalEur: cashEur + portfolioEur,
      cashEur,
      portfolioEur,
    },
    degradedSources,
  };
}
