import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../i18n';
import { CurrencyProvider, useCurrency } from './CurrencyContext';
import { PrivacyProvider } from './PrivacyContext';

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user: { display_currency: 'EUR' } }) }));
vi.mock('../api/foroba', () => ({ fetchFxRates: vi.fn().mockResolvedValue({ rates: { USD: 0.9 } }) }));

function Probe({ value }: { value: number }) {
  const { formatMoney } = useCurrency();
  return <p data-testid="amount">{formatMoney(value)}</p>;
}

function renderProbe(value: number) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <PrivacyProvider>
        <CurrencyProvider><Probe value={value} /></CurrencyProvider>
      </PrivacyProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => localStorage.clear());
afterEach(async () => { await i18n.changeLanguage('en'); });

describe('formatMoney', () => {
  it('formats with the UI language (en)', async () => {
    await i18n.changeLanguage('en');
    renderProbe(1234567.5);
    expect(screen.getByTestId('amount').textContent).toMatch(/€\s?1,234,567\.50/);
  });

  it('formats with the UI language (it)', async () => {
    await i18n.changeLanguage('it');
    renderProbe(1234567.5);
    expect(screen.getByTestId('amount').textContent).toMatch(/1\.234\.567,50\s?€/);
  });

  it('shows •••• when amounts are hidden', async () => {
    localStorage.setItem('kelen-privacy', 'true');
    renderProbe(1234.5);
    expect(screen.getByTestId('amount').textContent).toBe('••••');
  });

  it('never prints NaN or Infinity', () => {
    renderProbe(Number.NaN);
    expect(screen.getByTestId('amount').textContent).not.toMatch(/NaN|Infinity/);
  });
});
