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
      expect(url).toContain('/foroba-api/networth/summary');
      return jsonResponse({
        bank: { total_cents: 150_000, currency: 'EUR', account_count: 1 },
        investments: { total_eur: 2500, pnl_eur: 100, pnl_pct: 4.2, position_count: 3 },
        total_eur: 4000,
        history: [
          { date: '2026-07-15', bank_eur: 1400, investments_eur: 2400, total_eur: 3800 },
          { date: '2026-07-16', bank_eur: 1500, investments_eur: 2500, total_eur: 4000 },
        ],
        degraded: false,
        disclaimer: 'test',
      });
    }),
  );

  const result = await fetchNetWorth();

  expect(result.degradedSources).toEqual([]);
  expect(result.snapshot.cashEur).toBe(1500);
  expect(result.snapshot.portfolioEur).toBe(2500);
  expect(result.snapshot.totalEur).toBe(4000);
  expect(result.history).toHaveLength(2);
  expect(result.history[1]).toEqual({ date: '2026-07-16', totalEur: 4000 });
  expect(result.snapshot.delta1d).toBe(200);
});

test('one source failing is reported via degradedSources, other contributes normally', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      jsonResponse({
        bank: null,
        investments: { total_eur: 2500, pnl_eur: 100, pnl_pct: 4.2, position_count: 3 },
        total_eur: 2500,
        history: [{ date: '2026-07-16', bank_eur: 0, investments_eur: 2500, total_eur: 2500 }],
        degraded: true,
        disclaimer: 'test',
      }),
    ),
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
    vi.fn(async () =>
      jsonResponse({
        bank: null,
        investments: null,
        total_eur: 0,
        history: [],
        degraded: true,
        disclaimer: 'test',
      }),
    ),
  );

  await expect(fetchNetWorth()).resolves.toMatchObject({
    degradedSources: ['pazuru', 'tsumi'],
    snapshot: { cashEur: 0, portfolioEur: 0, totalEur: 0 },
  });
});

test('the backend itself being unreachable rejects (fetchJson throws, react-query handles retry/isError)', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    }),
  );

  await expect(fetchNetWorth()).rejects.toThrow();
});
