const BASE = import.meta.env.VITE_PAZURU_API_URL ?? '/pazuru-api';

export interface PazuruHealth {
  status: 'ok' | 'error' | 'unavailable';
}

export interface PazuruSummary {
  totalBalance: number;
  currency: string;
}

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

export async function fetchPazuruSummary(): Promise<PazuruSummary | null> {
  try {
    const res = await fetch(`${BASE}/api/analytics/summary`, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return null;
    const data = (await res.json()) as { total_balance_cents: number };
    return { totalBalance: (data.total_balance_cents ?? 0) / 100, currency: 'EUR' };
  } catch {
    return null;
  }
}
