import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ServiceStatusBar } from './ServiceStatusBar';

function renderBar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ServiceStatusBar />
    </QueryClientProvider>,
  );
}

describe('ServiceStatusBar', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  // pazuru#149 (PROD-PZR-D03): during the initial health check, `data` is
  // undefined for both services — this must render nothing, not a false
  // "offline" warning, until the checks actually resolve.
  it('renders nothing while health checks are still loading', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}));

    const { container } = renderBar();

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing once both services resolve healthy', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok' }),
    } as Response);

    const { container } = renderBar();

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it('shows an offline badge only for the service that failed, after resolving', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      if (String(url).includes('tsumi')) {
        throw new Error('network error');
      }
      return { ok: true, json: async () => ({ status: 'ok' }) } as Response;
    });

    renderBar();

    await waitFor(() => {
      expect(screen.getByText('Yiriba offline')).toBeInTheDocument();
    });
    expect(screen.queryByText('Naforo offline')).not.toBeInTheDocument();
  });
});
