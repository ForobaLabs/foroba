import { describe, expect, it, vi, beforeEach } from 'vitest';
import { createApiKey, listApiKeys, revokeApiKey } from './apiKeys';

describe('apiKeys api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('lists keys from GET /foroba-api/auth/api-keys', async () => {
    (fetch as any).mockResolvedValue({ ok: true, json: async () => [] });
    await listApiKeys();
    expect((fetch as any).mock.calls[0][0]).toBe('/foroba-api/auth/api-keys');
  });

  it('creates a key via POST and maps the raw response', async () => {
    (fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 1, label: 'n8n', key_prefix: 'fpk_abc', is_active: true,
        last_used_at: null, created_at: '2026-07-22T00:00:00Z', key: 'fpk_abc.secret123',
      }),
    });
    const created = await createApiKey('n8n');
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/foroba-api/auth/api-keys');
    expect(init.method).toBe('POST');
    expect(created.keyPrefix).toBe('fpk_abc');
    expect(created.key).toBe('fpk_abc.secret123');
  });

  it('revokes a key via DELETE', async () => {
    (fetch as any).mockResolvedValue({ ok: true, json: async () => { throw new Error('no body'); } });
    await revokeApiKey(1);
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/foroba-api/auth/api-keys/1');
    expect(init.method).toBe('DELETE');
  });
});
