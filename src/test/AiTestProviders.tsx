import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AiApiProvider, type AiApi } from '@foroba/ui';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

/** Inert AI API for tests that render a component containing an AiProviderToggle. */
function makeAiApi(): AiApi {
  return {
    getPrefs: vi.fn().mockResolvedValue([]),
    putPref: vi.fn().mockImplementation(async (p) => p),
    getConsents: vi.fn().mockResolvedValue([]),
    acceptConsent: vi.fn().mockResolvedValue(undefined),
    withdrawConsent: vi.fn().mockResolvedValue(undefined),
    getByok: vi.fn().mockResolvedValue([]),
    putByok: vi.fn(),
    deleteByok: vi.fn().mockResolvedValue(undefined),
    testByok: vi.fn(),
    getUsage: vi.fn().mockResolvedValue({ tier: 'free', allowance: 1, used: 0, percent: 0, unlimited: false }),
  } as unknown as AiApi;
}

export function AiTestProviders({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <AiApiProvider api={makeAiApi()}>{children}</AiApiProvider>
    </QueryClientProvider>
  );
}
