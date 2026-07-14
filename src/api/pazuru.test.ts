import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchPazuruHealth } from './pazuru';

describe('fetchPazuruHealth', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns the parsed body even on a 503 (backend-reported degraded)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      json: async () => ({ status: 'degraded', checks: { db: 'down' } }),
    } as Response);

    const result = await fetchPazuruHealth();
    expect(result.status).toBe('degraded');
  });

  it('returns unavailable on a real network failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network error'));

    const result = await fetchPazuruHealth();
    expect(result.status).toBe('unavailable');
  });
});
