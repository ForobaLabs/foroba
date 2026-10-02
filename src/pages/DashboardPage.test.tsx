import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../i18n';
import { PrivacyProvider } from '../contexts/PrivacyContext';
import { CurrencyProvider } from '../contexts/CurrencyContext';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const netWorth = vi.fn();
vi.mock('../hooks/useNetWorth', () => ({ useNetWorth: () => netWorth() }));
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user: { display_currency: 'EUR', show_debts: false } }) }));
vi.mock('../api/foroba', () => ({ fetchFxRates: vi.fn().mockResolvedValue({ rates: {} }) }));
vi.mock('../components/NetWorthChart', () => ({ NetWorthChart: () => null }));
vi.mock('../components/AllocationPie', () => ({ AllocationPie: () => null }));
vi.mock('../components/FinanceTipsCard', () => ({ FinanceTipsCard: () => null }));
vi.mock('../components/ServiceStatusBar', () => ({ ServiceStatusBar: () => null }));
vi.mock('../components/StreaksWidget', () => ({ StreaksWidget: () => null }));

import { DashboardPage } from './DashboardPage';

function ok(total: number, cash = total, portfolio = 0) {
  return {
    isLoading: false, isError: false, refetch: vi.fn(),
    data: { snapshot: { totalEur: total, cashEur: cash, portfolioEur: portfolio }, history: [], degradedSources: [] },
  };
}

function mount() {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <PrivacyProvider>
          <CurrencyProvider>
            <DashboardPage />
          </CurrencyProvider>
        </PrivacyProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('DashboardPage', () => {
  beforeEach(async () => { await i18n.changeLanguage('en'); localStorage.clear(); });
  afterEach(() => netWorth.mockReset());

  it('net-worth KPI in en: h1, subtitle, goal CTA, formatted total', () => {
    netWorth.mockReturnValue(ok(1234567.5, 1000000, 234567.5));
    mount();
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    expect(screen.getByText('Your money across all accounts, in one place')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Set a goal' })).toHaveAttribute('href', '/goals');
    expect(screen.getByTestId('net-worth')).toHaveTextContent('€1,234,567.50');
  });

  it('net-worth KPI in it: Italian copy and number format', async () => {
    await i18n.changeLanguage('it');
    netWorth.mockReturnValue(ok(1234567.5));
    mount();
    expect(screen.getByTestId('net-worth')).toHaveTextContent('1.234.567,50');
    expect(screen.getByText(/I tuoi soldi, su tutti i conti/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Crea un obiettivo' })).toBeInTheDocument();
  });

  it('hidden amounts never leak digits', () => {
    localStorage.setItem('kelen-privacy', 'true');
    netWorth.mockReturnValue(ok(1234567.5));
    mount();
    expect(screen.getByTestId('net-worth')).toHaveTextContent('••••');
    expect(screen.getByTestId('net-worth').textContent).not.toMatch(/\d/);
  });

  it('empty state offers adding an account', () => {
    netWorth.mockReturnValue(ok(0));
    mount();
    expect(screen.getByText('Nothing to show yet')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Add an account' })[0]).toHaveAttribute('href', '/accounts');
    expect(screen.queryByTestId('net-worth')).toBeNull();
  });

  it('error state is friendly and retries', async () => {
    const refetch = vi.fn();
    netWorth.mockReturnValue({ isLoading: false, isError: true, refetch, data: undefined });
    mount();
    expect(screen.getByText("We couldn't load your net worth")).toBeInTheDocument();
    expect(screen.queryByText(/failed/i)).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: /retry|try again/i }));
    expect(refetch).toHaveBeenCalled();
  });

  it('KPI cards are links, not role=button divs', () => {
    netWorth.mockReturnValue(ok(100, 60, 40));
    mount();
    expect(screen.getByRole('link', { name: /Cash \(Naforo\)/ })).toHaveAttribute('href', '/accounts');
    expect(screen.getByRole('link', { name: /Portfolio \(Yiriba\)/ })).toHaveAttribute('href', '/portfolio');
    expect(screen.queryAllByRole('button', { name: /Cash/ })).toHaveLength(0);
  });
});
