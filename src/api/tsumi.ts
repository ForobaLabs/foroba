const BASE = import.meta.env.VITE_TSUMI_API_URL ?? '/tsumi-api';

export interface TsumiHealth {
  status: 'ok' | 'error' | 'unavailable';
}

export interface TsumiSummary {
  totalValueEur: number;
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

export async function fetchTsumiHealth(): Promise<TsumiHealth> {
  return safeFetch(`${BASE}/health`, { status: 'unavailable' as const });
}

export async function fetchTsumiSummary(): Promise<TsumiSummary | null> {
  try {
    const res = await fetch(`${BASE}/api/portfolio/summary`, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return null;
    return (await res.json()) as TsumiSummary;
  } catch {
    return null;
  }
}
