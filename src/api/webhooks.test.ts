import { describe, expect, it, vi, beforeEach } from 'vitest';
import { createWebhook, deleteWebhook, listWebhooks, reactivateWebhook } from './webhooks';

describe('webhooks api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('lists webhooks from GET /foroba-api/auth/webhooks', async () => {
    (fetch as any).mockResolvedValue({ ok: true, json: async () => [] });
    await listWebhooks();
    expect((fetch as any).mock.calls[0][0]).toBe('/foroba-api/auth/webhooks');
  });

  it('creates a webhook via POST and maps the raw response', async () => {
    (fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 1, target_url: 'https://example.com/hook', is_active: true,
        consecutive_failures: 0, disabled_at: null, created_at: '2026-07-22T00:00:00Z',
        signing_secret: 'sig-secret-abc',
      }),
    });
    const created = await createWebhook('https://example.com/hook');
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/foroba-api/auth/webhooks');
    expect(init.method).toBe('POST');
    expect(created.signingSecret).toBe('sig-secret-abc');
  });

  it('reactivates a webhook via POST', async () => {
    (fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 1, target_url: 'https://example.com/hook', is_active: true,
        consecutive_failures: 0, disabled_at: null, created_at: '2026-07-22T00:00:00Z',
      }),
    });
    await reactivateWebhook(1);
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/foroba-api/auth/webhooks/1/reactivate');
    expect(init.method).toBe('POST');
  });

  it('deletes a webhook via DELETE', async () => {
    (fetch as any).mockResolvedValue({ ok: true, json: async () => { throw new Error('no body'); } });
    await deleteWebhook(1);
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/foroba-api/auth/webhooks/1');
    expect(init.method).toBe('DELETE');
  });
});
