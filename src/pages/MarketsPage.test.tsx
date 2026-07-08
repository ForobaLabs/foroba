import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { MarketsPage } from './MarketsPage';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <MarketsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        asset_class: 'crypto',
        gainers: [{ symbol: 'BTCUSDT', change_pct: 12.0 }],
        losers: [{ symbol: 'ETHUSDT', change_pct: -8.0 }],
        news: {
          symbol: 'BTCUSDT',
          items: [{ title: 'Bitcoin rallies', link: 'https://example.com', published: '', source: 'yahoo' }],
        },
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

test('renders news, top gainers/losers, and the disclaimer once the overview loads', async () => {
  renderPage();
  await waitFor(() =>
    expect(screen.getByText(/not financial advice/i)).toBeInTheDocument(),
  );
  expect(screen.getByText('Bitcoin rallies')).toBeInTheDocument();
  expect(screen.getByText('BTCUSDT')).toBeInTheDocument();
  expect(screen.getByText('ETHUSDT')).toBeInTheDocument();
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
