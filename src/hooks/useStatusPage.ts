import type { HealthStatus } from '@foroba/ui';
import { useForobaHealth, usePazuruHealth, useTsumiHealth } from './useServiceHealth';

export interface AppStatus {
  name: string;
  status: HealthStatus;
  lastChecked: string | null;
}

function toHealthStatus(query: {
  data?: { status: string };
  isError: boolean;
  dataUpdatedAt: number;
}): AppStatus['status'] {
  if (query.isError) return 'unreachable';
  const backendStatus = query.data?.status;
  if (backendStatus === 'ok') return 'ok';
  if (backendStatus === 'degraded') return 'down';
  if (backendStatus === 'unavailable') return 'unreachable';
  return 'unknown';
}

/**
 * Combines the per-app health queries (each already isolated by react-query —
 * one query failing never affects the others) into the shape StatusPage/
 * AdminStatusPanel need. 30s refresh comes from each underlying query hook.
 */
export function useStatusPage() {
  const foroba = useForobaHealth();
  const pazuru = usePazuruHealth();
  const tsumi = useTsumiHealth();

  const apps: AppStatus[] = [
    {
      name: 'Foroba',
      status: toHealthStatus(foroba),
      lastChecked: foroba.dataUpdatedAt ? new Date(foroba.dataUpdatedAt).toISOString() : null,
    },
    {
      name: 'Naforo',
      status: toHealthStatus(pazuru),
      lastChecked: pazuru.dataUpdatedAt ? new Date(pazuru.dataUpdatedAt).toISOString() : null,
    },
    {
      name: 'Yiriba',
      status: toHealthStatus(tsumi),
      lastChecked: tsumi.dataUpdatedAt ? new Date(tsumi.dataUpdatedAt).toISOString() : null,
    },
  ];

  return { apps } as const;
}
