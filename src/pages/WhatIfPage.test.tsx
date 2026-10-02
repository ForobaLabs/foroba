import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../i18n';
import i18n from '../i18n';

const simulate = vi.fn();
vi.mock('../api/whatif', () => ({
  simulateWhatIf: (...a: unknown[]) => simulate(...a),
  listWhatIfScenarios: vi.fn().mockResolvedValue([]),
  createWhatIfScenario: vi.fn(),
  getWhatIfScenario: vi.fn(),
  deleteWhatIfScenario: vi.fn(),
}));
vi.mock('../api/pazuru', () => ({ fetchPazuruGoals: vi.fn().mockResolvedValue([]) }));
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user: { show_debts: false } }) }));
vi.mock('../components/JeliInterpretButton', () => ({ JeliInterpretButton: () => null }));
vi.mock('@foroba/ui', async () => {
  const actual = await vi.importActual<typeof import('@foroba/ui')>('@foroba/ui');
  return { ...actual, useEntitlement: () => ({ loading: false, visible: true, unlocked: true }) };
});

import { WhatIfPage } from './WhatIfPage';

function result(total: number) {
  return {
    points: [
      { month: 0, resolution: 'monthly', bankEur: 1000, investmentsEur: 0, totalEur: 1000 },
      { month: 120, resolution: 'yearly', bankEur: total, investmentsEur: 0, totalEur: total },
    ],
    goalImpacts: [], degraded: false, disclaimer: 'Informational only.',
  };
}

async function settle(ms = 250) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
}

beforeEach(async () => {
  vi.useFakeTimers();
  simulate.mockReset();
  simulate.mockImplementation(async (p: { incomeDeltaCents?: number }) => result(p.incomeDeltaCents ? 50_000 : 10_000));
  await i18n.changeLanguage('en');
});
afterEach(() => vi.useRealTimers());

describe('WhatIfPage', () => {
  it('shows a default scenario result without any click', async () => {
    render(<WhatIfPage />);
    await settle();
    expect(simulate).toHaveBeenCalled();
    expect(screen.getByText(/In 10 years you could have/)).toBeInTheDocument();
    expect(screen.getByText(/€50,000/)).toBeInTheDocument();
  });

  it('updates the preview 250 ms after an input changes, not before', async () => {
    render(<WhatIfPage />);
    await settle();
    simulate.mockClear();
    fireEvent.change(screen.getByLabelText(/Extra money per month/), { target: { value: '400' } });
    await settle(200);
    expect(simulate).not.toHaveBeenCalled();
    await settle(60);
    expect(simulate).toHaveBeenCalled();
    expect(simulate.mock.calls[0][0].incomeDeltaCents).toBe(40_000);
  });

  it('accepts a comma decimal rate and converts years to months', async () => {
    render(<WhatIfPage />);
    await settle();
    simulate.mockClear();
    fireEvent.change(screen.getByLabelText(/Yearly return/), { target: { value: '4,5' } });
    fireEvent.change(screen.getByLabelText(/^Years/), { target: { value: '3' } });
    await settle();
    const p = simulate.mock.calls[0][0];
    expect(p.investmentGrowthRatePct).toBe(4.5);
    expect(p.horizonMonths).toBe(36);
  });

  it('shows a human message, sets aria-invalid, and never calls the API for invalid input', async () => {
    render(<WhatIfPage />);
    await settle();
    simulate.mockClear();
    const amount = screen.getByLabelText(/Extra money per month/);
    fireEvent.change(amount, { target: { value: '0' } });
    await settle();
    expect(screen.getByText('Enter an amount greater than 0')).toBeInTheDocument();
    expect(amount).toHaveAttribute('aria-invalid', 'true');
    expect(simulate).not.toHaveBeenCalled();
  });

  it.each([
    ['Years', '61', 'Enter a whole number of years from 1 to 60'],
    ['Yearly return', '51', 'Enter a yearly return between -50% and 50%'],
    ['Extra money per month', '1000000000', 'Enter an amount of 1,000,000 or less'],
  ])('rejects %s = %s', async (label, value, message) => {
    render(<WhatIfPage />);
    await settle();
    fireEvent.change(screen.getByLabelText(new RegExp(`^${label}`)), { target: { value } });
    await settle();
    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it('Run focuses the first invalid field', async () => {
    render(<WhatIfPage />);
    await settle();
    fireEvent.change(screen.getByLabelText(/^Years/), { target: { value: '99' } });
    fireEvent.change(screen.getByLabelText(/Yearly return/), { target: { value: '99' } });
    fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
    expect(screen.getByLabelText(/^Years/)).toHaveFocus();
  });

  it('category chips prefill the inputs', async () => {
    render(<WhatIfPage />);
    await settle();
    fireEvent.click(screen.getByRole('button', { name: 'Invest' }));
    expect(screen.getByLabelText(/Extra money per month/)).toHaveValue('250');
    expect(screen.getByLabelText(/^Years/)).toHaveValue('20');
    expect(screen.getByLabelText(/Yearly return/)).toHaveValue('7');
    expect(screen.getByRole('button', { name: 'Invest' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Pay debt' }));
    expect(screen.getByLabelText(/Yearly return/)).toHaveValue('0');
  });

  it('API failure shows the friendly error with Retry, and Retry recovers', async () => {
    simulate.mockRejectedValue(new Error('boom'));
    render(<WhatIfPage />);
    await settle();
    expect(
      screen.getByText("We couldn't run this simulation. Check your connection and try again."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Simulation failed/i)).toBeNull();
    simulate.mockImplementation(async () => result(70_000));
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await settle(0);
    expect(screen.getByText(/€70,000/)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('keeps showing the last good result while a later request fails, with the error beside it', async () => {
    render(<WhatIfPage />);
    await settle();
    simulate.mockRejectedValue(new Error('boom'));
    fireEvent.change(screen.getByLabelText(/Extra money per month/), { target: { value: '300' } });
    await settle();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/€50,000/)).toBeInTheDocument();
  });

  it('ignores a slow stale response that arrives after a newer one', async () => {
    let releaseFirst: (v: unknown) => void = () => {};
    simulate.mockReset();
    simulate.mockImplementationOnce(() => new Promise((r) => { releaseFirst = r; }));
    simulate.mockImplementation(async () => result(99_000));
    render(<WhatIfPage />);
    await settle(); // first request (scenario) pending
    fireEvent.change(screen.getByLabelText(/Extra money per month/), { target: { value: '500' } });
    await settle();
    await act(async () => { releaseFirst(result(1_234)); });
    expect(screen.getByText(/€99,000/)).toBeInTheDocument();
    expect(screen.queryByText(/€1,234/)).toBeNull();
  });

  it('renders in Italian with Italian validation copy', async () => {
    await i18n.changeLanguage('it');
    render(<WhatIfPage />);
    await settle();
    fireEvent.change(screen.getByLabelText(/Soldi in più al mese/), { target: { value: '0' } });
    await settle();
    expect(screen.getByText('Inserisci un importo maggiore di 0')).toBeInTheDocument();
  });
});

describe('copy guard', () => {
  function walk(dir: string, out: string[] = []): string[] {
    for (const f of readdirSync(dir)) {
      const p = join(dir, f);
      if (statSync(p).isDirectory()) walk(p, out);
      else if (/\.(tsx?|json)$/.test(f) && !/\.test\.tsx?$/.test(f)) out.push(p);
    }
    return out;
  }
  it('the string "Simulation failed" does not exist in src/', () => {
    const offenders = walk(join(__dirname, '..')).filter((p) => /Simulation failed/i.test(readFileSync(p, 'utf8')));
    expect(offenders).toEqual([]);
  });
});
