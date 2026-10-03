import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import i18n from '../i18n';
import { CurrencyProvider } from '../contexts/CurrencyContext';
import { PrivacyProvider } from '../contexts/PrivacyContext';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AllocationPie } from './AllocationPie';

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user: { display_currency: 'EUR' } }) }));
vi.mock('../api/foroba', () => ({ fetchFxRates: vi.fn().mockResolvedValue({ rates: {} }) }));

function renderPie(cashEur: number, portfolioEur: number) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <PrivacyProvider>
        <CurrencyProvider>
          <AllocationPie cashEur={cashEur} portfolioEur={portfolioEur} />
        </CurrencyProvider>
      </PrivacyProvider>
    </QueryClientProvider>,
  );
}

afterEach(async () => {
  await i18n.changeLanguage('en');
});

describe('AllocationPie', () => {
  it('localises the empty state', async () => {
    await i18n.changeLanguage('it');
    renderPie(0, 0);
    expect(screen.getByText('Ancora niente da mostrare.')).toBeTruthy();
  });

  it('shows only the non-zero slice at 100%', async () => {
    await i18n.changeLanguage('en');
    renderPie(500, 0);
    expect(screen.getByText('Cash (Naforo)')).toBeTruthy();
    expect(screen.queryByText('Portfolio (Yiriba)')).toBeNull();
    expect(screen.getByText('100.0%')).toBeTruthy();
  });

  it('localises slice labels', async () => {
    await i18n.changeLanguage('it');
    renderPie(100, 100);
    expect(screen.getByText('Liquidità (Naforo)')).toBeTruthy();
    expect(screen.getByText('Portafoglio (Yiriba)')).toBeTruthy();
  });
});
