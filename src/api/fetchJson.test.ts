import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { fetchJson } from './fetchJson';

beforeEach(() => {
  vi.useRealTimers();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test('resolves with the parsed JSON body on a 2xx response', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => ({ hello: 'world' }),
    })),
  );

  await expect(fetchJson<{ hello: string }>('https://example.test/ok')).resolves.toEqual({
    hello: 'world',
  });
});

test('throws a descriptive Error on a non-2xx response instead of swallowing it', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      json: async () => ({}),
    })),
  );

  await expect(fetchJson('https://example.test/down')).rejects.toThrow(/503/);
});

test('throws (does not swallow) on network failure', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    }),
  );

  await expect(fetchJson('https://example.test/unreachable')).rejects.toThrow(
    /Failed to fetch/,
  );
});

test('throws a descriptive Error when a 2xx response body is not valid JSON', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => {
        throw new SyntaxError('Unexpected token < in JSON at position 0');
      },
    })),
  );

  await expect(fetchJson('https://example.test/bad-json')).rejects.toThrow(/invalid JSON/);
});

test('passes a timeout-derived AbortSignal through to fetch by default', async () => {
  const fetchMock = vi.fn(async () => ({
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => ({}),
  }));
  vi.stubGlobal('fetch', fetchMock);

  await fetchJson('https://example.test/ok', { timeoutMs: 1234 });

  expect(fetchMock).toHaveBeenCalledTimes(1);
  const call = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
  const [, init] = call;
  expect(init.signal).toBeInstanceOf(AbortSignal);
});
