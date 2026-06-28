import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { MarketsPage } from './MarketsPage';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MarketsPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        symbol: 'BTCUSDT',
        asset_class: 'crypto',
        rating: { label: 'buy', score: 0.42 },
        sentiment: { sentiment: 'positive' },
        movers: [{ symbol: 'ETHUSDT', change_pct: 5.0 }],
        degraded: false,
        disclaimer: 'Informational only — not financial advice.',
      }),
    })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test('renders the Markets heading', () => {
  renderPage();
  expect(screen.getByText('Markets')).toBeInTheDocument();
});

test('renders the disclaimer once the snapshot loads', async () => {
  renderPage();
  await waitFor(() =>
    expect(screen.getByText(/not financial advice/i)).toBeInTheDocument(),
  );
});
