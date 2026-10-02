import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import i18n from '../i18n';
import { BillingSection } from './BillingSection';

function renderSection() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <BillingSection />
    </QueryClientProvider>,
  );
}

function stubFetch(status: unknown, checkout?: () => Response) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.endsWith('/billing/status')) return Promise.resolve(new Response(JSON.stringify(status)));
      if (url.endsWith('/billing/checkout-session') && checkout) return Promise.resolve(checkout());
      return Promise.reject(new Error(`unexpected ${url}`));
    }),
  );
}

beforeAll(() => i18n.changeLanguage('en'));
afterEach(() => vi.unstubAllGlobals());

describe('BillingSection', () => {
  it('says paid plans are unavailable while billing is disabled and offers no purchase button', async () => {
    stubFetch({ enabled: false, subscription: null });
    renderSection();
    expect(await screen.findByText(/not available yet/i)).toBeInTheDocument();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('renders nothing when the status call fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('{}', { status: 500 }))));
    const { container } = renderSection();
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the subscription status when one exists', async () => {
    stubFetch({ enabled: true, subscription: { status: 'active', current_period_end: null, cancel_at_period_end: true } });
    renderSection();
    expect(await screen.findByText(/active/)).toBeInTheDocument();
  });

  it('refuses a non-https checkout url and shows an error', async () => {
    stubFetch({ enabled: true, subscription: null }, () => new Response(JSON.stringify({ url: 'javascript:alert(1)' })));
    renderSection();
    await userEvent.click(await screen.findByRole('button', { name: /continue to checkout/i }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('sends the plan and period picked by the person, defaulting to premium monthly', async () => {
    const bodies: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init?: RequestInit) => {
        if (url.endsWith('/billing/status')) return Promise.resolve(new Response(JSON.stringify({ enabled: true, subscription: null })));
        bodies.push(String(init?.body));
        return Promise.resolve(new Response('{}', { status: 501 }));
      }),
    );
    renderSection();
    const go = await screen.findByRole('button', { name: /continue to checkout/i });
    expect(screen.getByRole('radio', { name: 'Premium' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'Monthly' })).toBeChecked();
    await userEvent.click(go);
    await screen.findByRole('alert');
    await userEvent.click(screen.getByRole('radio', { name: 'Expert' }));
    await userEvent.click(screen.getByRole('radio', { name: 'Yearly' }));
    await userEvent.click(go);
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(JSON.parse(bodies[0])).toEqual({ plan: 'premium_monthly' });
    expect(JSON.parse(bodies[1])).toEqual({ plan: 'expert_yearly' });
  });
});
