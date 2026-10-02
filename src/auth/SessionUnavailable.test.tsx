import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '../i18n';
import { AuthProvider, useAuth } from './AuthProvider';
import { SessionUnavailable } from './SessionUnavailable';

function Probe() {
  const { user, loading, unavailable } = useAuth();
  return <p>{loading ? 'loading' : unavailable ? 'unavailable' : user ? 'user' : 'anonymous'}</p>;
}

function renderWith(fetchImpl: () => Promise<Partial<Response>>) {
  globalThis.fetch = vi.fn(fetchImpl) as unknown as typeof fetch;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AuthProvider><Probe /></AuthProvider></QueryClientProvider>);
}

describe('session outage vs signed-out', () => {
  it('flags unavailable (not anonymous) when /auth/me fails with a server error', async () => {
    renderWith(async () => ({ ok: false, status: 503 }));
    await waitFor(() => expect(screen.getByText('unavailable')).toBeInTheDocument());
  });

  it('flags unavailable when the network is down', async () => {
    renderWith(async () => { throw new TypeError('Failed to fetch'); });
    await waitFor(() => expect(screen.getByText('unavailable')).toBeInTheDocument());
  });

  it('stays anonymous on a plain 401', async () => {
    renderWith(async () => ({ ok: false, status: 401 }));
    await waitFor(() => expect(screen.getByText('anonymous')).toBeInTheDocument());
  });

  it('renders a retry screen that calls onRetry', async () => {
    const onRetry = vi.fn();
    render(<SessionUnavailable onRetry={onRetry} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(onRetry).toHaveBeenCalled();
  });
});
