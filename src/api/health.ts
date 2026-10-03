/**
 * Shared health-probe fetch helpers, used by foroba.ts/pazuru.ts/tsumi.ts.
 * Kept in their own module (not foroba.ts) so pazuru.ts/tsumi.ts can import
 * it without a runtime circular dependency (foroba.ts imports fetchers FROM
 * pazuru.ts/tsumi.ts for net-worth aggregation).
 */

export interface DependencyStatus {
  status: 'ok' | 'degraded' | 'unknown';
  last_checked: string | null;
}

export interface DetailedHealth {
  status: 'ok' | 'degraded' | 'unavailable';
  checks?: { db: 'ok' | 'down' };
  dependencies: Record<string, DependencyStatus>;
}

// Health endpoints return a valid JSON body even at 503 (backend-reported
// "degraded"), unlike other endpoints where a non-2xx means no usable body.
// A 429 means the service answered: report it online (throttled), never offline
// (audit 2026-10-02 W1). Only fall back on a genuine network-level failure.
export async function fetchHealthBody<T>(url: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (res.status === 429) return { status: 'ok', throttled: true } as T;
    return (await res.json()) as T;
  } catch {
    return fallback;
  }
}

function isDetailedHealth(body: unknown): body is DetailedHealth {
  return (
    typeof body === 'object' &&
    body !== null &&
    'dependencies' in body &&
    typeof (body as { dependencies: unknown }).dependencies === 'object' &&
    (body as { dependencies: unknown }).dependencies !== null
  );
}

// Unlike /health, /health/detailed is an authenticated+admin-gated endpoint —
// a 401/403 (unauthenticated user, or a non-admin session on a sub-app whose
// admin flag hasn't synced) returns FastAPI's generic {detail: "..."} error
// shape, not a DetailedHealth body. Validate the shape before trusting it so
// a permission mismatch on one sub-app can't crash the whole Status panel.
export async function fetchDetailedHealthBody(
  url: string,
  fallback: DetailedHealth,
): Promise<DetailedHealth> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
    const body: unknown = await res.json();
    return isDetailedHealth(body) ? body : fallback;
  } catch {
    return fallback;
  }
}
