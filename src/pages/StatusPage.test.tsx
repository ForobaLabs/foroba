import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StatusPage } from './StatusPage';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <StatusPage />
    </QueryClientProvider>,
  );
}

describe('StatusPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders all 3 apps as operational when all healthy', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok', checks: { db: 'ok' } }),
    } as Response);

    renderPage();

    await waitFor(() => {
      expect(screen.getAllByText('Operational')).toHaveLength(3);
    });
  });

  it('shows one app as unreachable while the other two stay ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      if (String(url).includes('tsumi')) {
        throw new Error('network error');
      }
      return { ok: true, json: async () => ({ status: 'ok', checks: { db: 'ok' } }) } as Response;
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Unreachable')).toBeInTheDocument();
      expect(screen.getAllByText('Operational')).toHaveLength(2);
    });
  });
});
