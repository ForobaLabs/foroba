import { afterEach, expect, test, vi } from 'vitest';
import { fetchNetWorth } from './foroba';

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown) {
  return { ok: true, status: 200, statusText: 'OK', json: async () => body };
}

test('resolves with both values and no degraded sources when both back-ends are healthy', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.includes('analytics/summary')) return jsonResponse({ total_balance_cents: 150_000 });
      if (url.includes('portfolio/summary')) return jsonResponse({ total_eur: 2500 });
      throw new Error(`unexpected url ${url}`);
    }),
  );

  const result = await fetchNetWorth();

  expect(result.degradedSources).toEqual([]);
  expect(result.snapshot.cashEur).toBe(1500);
  expect(result.snapshot.portfolioEur).toBe(2500);
  expect(result.snapshot.totalEur).toBe(4000);
});

test('one source failing does not block the other (Promise.allSettled behavior)', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.includes('analytics/summary')) {
        return { ok: false, status: 503, statusText: 'Service Unavailable', json: async () => ({}) };
      }
      if (url.includes('portfolio/summary')) return jsonResponse({ total_eur: 2500 });
      throw new Error(`unexpected url ${url}`);
    }),
  );

  const result = await fetchNetWorth();

  expect(result.degradedSources).toEqual(['pazuru']);
  expect(result.snapshot.cashEur).toBe(0);
  expect(result.snapshot.portfolioEur).toBe(2500);
  expect(result.snapshot.totalEur).toBe(2500);
});

test('both sources failing resolves (does not throw) with both flagged as degraded', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    }),
  );

  await expect(fetchNetWorth()).resolves.toMatchObject({
    degradedSources: ['pazuru', 'tsumi'],
    snapshot: { cashEur: 0, portfolioEur: 0, totalEur: 0 },
  });
});
