/**
 * Shared fetch wrapper for the Foroba shell's cross-app data fetchers
 * (Pazuru summary, Tsumi summary, Foroba markets snapshot, ...).
 *
 * Unlike the legacy per-call `try { fetch } catch { return fallback }`
 * pattern, this wrapper ALWAYS throws a real `Error` on network failure
 * or a non-2xx response instead of swallowing it into a sentinel value.
 * This lets TanStack Query's `retry`/`retryDelay` (configured once,
 * globally, in `main.tsx`) actually engage, and lets components
 * distinguish loading / empty / error via `isError` instead of guessing
 * from `data === null`.
 *
 * This wrapper intentionally does NOT implement its own retry loop —
 * react-query is the single retry orchestrator for every call site that
 * uses it (via `useQuery`). Keep this a single-attempt "fetch + parse +
 * throw-on-failure" primitive.
 */

export interface FetchJsonOptions extends Omit<RequestInit, 'signal'> {
  /** Abort timeout in ms. Ignored if `signal` is explicitly provided. */
  timeoutMs?: number;
  /** Escape hatch to supply a custom AbortSignal instead of the timeout one. */
  signal?: AbortSignal;
}

const DEFAULT_TIMEOUT_MS = 5000;

export async function fetchJson<T>(url: string, options: FetchJsonOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal, ...init } = options;

  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      signal: signal ?? AbortSignal.timeout(timeoutMs),
    });
  } catch (cause) {
    const reason = cause instanceof Error ? cause.message : String(cause);
    throw new Error(`Request to ${url} failed: ${reason}`, { cause });
  }

  if (!res.ok) {
    throw new Error(`Request to ${url} failed with status ${res.status} ${res.statusText}`.trim());
  }

  try {
    return (await res.json()) as T;
  } catch (cause) {
    const reason = cause instanceof Error ? cause.message : String(cause);
    throw new Error(`Request to ${url} returned invalid JSON: ${reason}`, { cause });
  }
}
