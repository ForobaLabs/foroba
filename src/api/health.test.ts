import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchHealthBody } from './health';

afterEach(() => vi.unstubAllGlobals());

describe('fetchHealthBody', () => {
  it('treats 429 as online-but-throttled, never as unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"error":"Rate limit exceeded"}', { status: 429 })));
    const body = await fetchHealthBody('/x/health', { status: 'unavailable' as const });
    expect(body).toEqual({ status: 'ok', throttled: true });
  });

  it('keeps the 503 degraded body', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"status":"degraded"}', { status: 503 })));
    expect(await fetchHealthBody('/x/health', { status: 'unavailable' as const })).toEqual({ status: 'degraded' });
  });

  it('falls back on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('network'); }));
    expect(await fetchHealthBody('/x/health', { status: 'unavailable' as const })).toEqual({ status: 'unavailable' });
  });
});
