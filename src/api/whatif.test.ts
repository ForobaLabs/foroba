import { describe, expect, it, vi, beforeEach } from 'vitest';
import { simulateWhatIf, listWhatIfScenarios, createWhatIfScenario } from './whatif';

describe('whatif api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('posts params to /foroba-api/whatif/simulate', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ points: [], goal_impacts: [], degraded: false, disclaimer: 'x' }),
    } as Response);
    await simulateWhatIf({ horizonMonths: 12 });
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe('/foroba-api/whatif/simulate');
    expect((init as RequestInit).method).toBe('POST');
  });

  it('lists scenarios from GET /foroba-api/whatif/scenarios', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => [] } as Response);
    await listWhatIfScenarios();
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe('/foroba-api/whatif/scenarios');
  });

  it('creates a scenario via POST', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, name: 'x', horizonMonths: 12, params: {}, createdAt: '', updatedAt: '' }),
    } as Response);
    await createWhatIfScenario({ name: 'x', horizonMonths: 12, params: { horizonMonths: 12 } });
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init as RequestInit).method).toBe('POST');
  });
});
