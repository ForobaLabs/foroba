import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '../i18n';
import { SharedGoalPage } from './SharedGoalPage';

const renderPage = () =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/share/goal/tok']}>
        <Routes><Route path="/share/goal/:token" element={<SharedGoalPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

afterEach(() => vi.unstubAllGlobals());

describe('SharedGoalPage', () => {
  it('renders the shared projection without auth', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      name: 'Trip', currency: 'EUR', saved_cents: 100000, target_cents: 300000, monthly_cents: 50000,
      rate_pct: 0, series: [100000, 150000, 200000, 250000, 300000], months_to_target: 4, exp: 4102444800,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Trip' })).toBeTruthy();
    expect(screen.getByText(/4 months/)).toBeTruthy();
  });

  it('shows the invalid state for a bad token', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Invalid or expired share link' }), { status: 400, headers: { 'Content-Type': 'application/json' } })));
    renderPage();
    expect(await screen.findByText(/isn't valid/i)).toBeTruthy();
  });
});
