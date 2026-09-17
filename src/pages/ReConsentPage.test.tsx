import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, expect, test, vi } from 'vitest';
import { ReConsentPage } from './ReConsentPage';

function renderPage(qc: QueryClient) {
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/re-consent']}>
        <Routes>
          <Route path="/re-consent" element={<ReConsentPage />} />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockFetchByUrl(handlers: Record<string, () => unknown>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: RequestInfo | URL) => {
      const path = String(url);
      const match = Object.keys(handlers).find((suffix) => path.endsWith(suffix));
      if (!match) throw new Error(`unhandled fetch: ${path}`);
      const body = handlers[match]();
      return { ok: true, json: async () => body } as Response;
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test(
  'FOR-D07: accepting on the first click navigates to / immediately, without needing a stale-cache-driven second click',
  async () => {
    mockFetchByUrl({
      '/auth/consents/accept': () => null,
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    // Seed the same stale value App.tsx's ['consents-status'] query would have held
    // (this is what handleAccept must overwrite synchronously, not just invalidate).
    qc.setQueryData(['consents-status'], { terms_of_service: false, privacy_policy: false });

    renderPage(qc);

    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: /accept and continue/i }));

    await waitFor(() => expect(screen.getByText('Home')).toBeInTheDocument());

    // The query cache itself must already reflect the accepted state (not just
    // "invalidated and refetching") so <App>'s very first render after navigation
    // reads correct data.
    expect(qc.getQueryData(['consents-status'])).toEqual({
      terms_of_service: true,
      privacy_policy: true,
    });
  },
);

test(
  'routing gap: an already-fully-consented user who visits /re-consent directly is redirected to / instead of being shown the form again',
  async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(['consents-status'], { terms_of_service: true, privacy_policy: true });

    renderPage(qc);

    await waitFor(() => expect(screen.getByText('Home')).toBeInTheDocument());
  },
);
