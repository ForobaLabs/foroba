import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
        sentiment: {
          symbol: 'BTCUSDT',
          sentiment: { score: 0.42, label: 'positive', positive: 8, neutral: 16, negative: 6, count: 30 },
          sample_headlines: [],
        },
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

test('renders ErrorState with a working Retry button when the query fails', async () => {
  const fetchMock = vi.fn(async () => ({
    ok: false,
    status: 502,
    statusText: 'Bad Gateway',
    json: async () => ({}),
  }));
  vi.stubGlobal('fetch', fetchMock);

  renderPage();

  await waitFor(() =>
    expect(
      screen.getByText(/market data is currently unavailable/i),
    ).toBeInTheDocument(),
  );

  const callsBeforeRetry = fetchMock.mock.calls.length;
  fireEvent.click(screen.getByRole('button', { name: /retry/i }));

  await waitFor(() =>
    expect(fetchMock.mock.calls.length).toBeGreaterThan(callsBeforeRetry),
  );
});
