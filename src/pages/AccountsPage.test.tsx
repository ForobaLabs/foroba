import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../i18n';
import { AccountsPage } from './AccountsPage';

const health = { data: { status: 'ok' }, isLoading: false };
let accounts: { data: unknown[]; isLoading: boolean; isError: boolean; refetch: () => void };

vi.mock('../hooks/useServiceHealth', () => ({
  usePazuruHealth: () => health,
  useAccountsList: () => accounts,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <AccountsPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  accounts = { data: [], isLoading: false, isError: false, refetch: vi.fn() };
});

describe('AccountsPage', () => {
  it('shows a single connect CTA and no export when there are no accounts', () => {
    renderPage();
    expect(screen.getAllByRole('button', { name: /connect/i })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: /export/i })).toBeNull();
  });

  it('shows the header actions once accounts exist', () => {
    accounts = {
      data: [{ id: 1, bankName: 'revolut', displayName: 'Main', currency: 'EUR', balance: 10 }],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    };
    renderPage();
    expect(screen.getAllByRole('button', { name: /connect/i })).toHaveLength(1);
    expect(screen.getByRole('button', { name: /export/i })).toBeTruthy();
  });

  it('renders the page title as the single h1', () => {
    renderPage();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  });
});
