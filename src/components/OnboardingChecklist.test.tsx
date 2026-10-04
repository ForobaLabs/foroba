import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../i18n';

const accounts = vi.fn();
const goals = vi.fn();
let user: Record<string, unknown> | null = null;

vi.mock('../api/pazuru', () => ({ fetchPazuruAccounts: () => accounts(), fetchPazuruGoals: () => goals() }));
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user }) }));

import { OnboardingChecklist } from './OnboardingChecklist';

function mount() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><OnboardingChecklist /></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('OnboardingChecklist', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
    localStorage.clear();
    user = { totp_enabled: false, email_otp_enabled: false, webauthn_enabled: false, email_verified: true };
    accounts.mockResolvedValue([]);
    goals.mockResolvedValue([]);
  });

  it('lists the open steps as links and counts progress', async () => {
    mount();
    expect(await screen.findByText('1 of 4 done')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Turn on two-step verification' })).toHaveAttribute('href', '/settings');
    expect(screen.getByRole('link', { name: 'Set your first goal' })).toHaveAttribute('href', '/goals');
    expect(screen.queryByRole('link', { name: 'Verify your email' })).toBeNull();
  });

  it('dismiss hides the card and persists', async () => {
    mount();
    await userEvent.click(await screen.findByRole('button', { name: /dismiss/i }));
    expect(screen.queryByText('Get started')).toBeNull();
    expect(localStorage.getItem('foroba.checklist.dismissed')).toBe('true');
  });

  it('renders nothing when every step is done', async () => {
    user = { ...user, totp_enabled: true };
    accounts.mockResolvedValue([{ id: 1 }]);
    goals.mockResolvedValue([{ id: 1 }]);
    mount();
    await waitFor(() => { expect(goals).toHaveBeenCalled(); });
    expect(screen.queryByText('Get started')).toBeNull();
  });

  it('renders nothing when the counts cannot be loaded', async () => {
    accounts.mockRejectedValue(new Error('428'));
    mount();
    await waitFor(() => { expect(accounts).toHaveBeenCalled(); });
    expect(screen.queryByText('Get started')).toBeNull();
  });
});
