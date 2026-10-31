import '../i18n';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { AiApiProvider, type AiApi } from '@foroba/ui';
import { JeliInterpretButton } from '../components/JeliInterpretButton';
import { JeliPanel } from '../components/shell/JeliPanel';
import { FOROBA_FAQ } from '../data/faq';
import { PRIVACY_POLICY } from '../data/legal';
import { readAiMeta } from './aiMeta';

function makeApi(): AiApi {
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

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AiApiProvider api={makeApi()}>{ui}</AiApiProvider>
    </QueryClientProvider>,
  );
}

const noop = () => {};
const reply = (meta?: { provider: string; model?: string; notice?: string | null }) => [
  { role: 'user' as const, content: 'hi', timestamp: new Date() },
  { role: 'assistant' as const, content: 'hello', timestamp: new Date(), meta },
];

describe('Foroba AI touchpoints', () => {
  it('every_ai_touchpoint_renders_toggle (jeli panel)', async () => {
    wrap(<JeliPanel messages={[]} streaming={false} onSend={noop} onStop={noop} onReset={noop} />);
    expect(await screen.findByRole('radiogroup', { name: /AI/ })).toBeInTheDocument();
  });

  it('every_ai_touchpoint_renders_toggle (interpret button)', async () => {
    wrap(<JeliInterpretButton contextLabel="x" buildContext={() => 'y'} />);
    expect(await screen.findByRole('radiogroup', { name: /AI/ })).toBeInTheDocument();
  });

  it('reply_shows_badge', () => {
    wrap(
      <JeliPanel
        messages={reply({ provider: 'cloudflare', model: 'm', notice: null })}
        streaming={false}
        onSend={noop}
        onStop={noop}
        onReset={noop}
      />,
    );
    expect(screen.getByText(/Cloud · Cloudflare/)).toBeInTheDocument();
  });

  it('reply_with_notice_shows_banner', () => {
    wrap(
      <JeliPanel
        messages={reply({ provider: 'local', notice: 'cloud_unavailable' })}
        streaming={false}
        onSend={noop}
        onStop={noop}
        onReset={noop}
      />,
    );
    expect(screen.getByRole('status')).toHaveTextContent(/Cloud AI is not available/);
  });

  it('readAiMeta parses the X-AI-* response headers', () => {
    const h = new Headers({ 'X-AI-Provider': 'openai', 'X-AI-Model': 'gpt-4o-mini', 'X-AI-Notice': '' });
    expect(readAiMeta(h)).toEqual({ provider: 'openai', model: 'gpt-4o-mini', notice: null });
    expect(readAiMeta(new Headers())).toBeNull();
  });

  it('no_local_only_claims', () => {
    const text = JSON.stringify([FOROBA_FAQ, PRIVACY_POLICY]);
    expect(text).not.toMatch(/on your device|sul tuo dispositivo|never leave|no data ever leaves/i);
  });
});
