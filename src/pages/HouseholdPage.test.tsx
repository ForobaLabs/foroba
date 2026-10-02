import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../i18n';

const useHousehold = vi.fn();
vi.mock('../auth/useHousehold', () => ({ useHousehold: () => useHousehold() }));

import { HouseholdPage } from './HouseholdPage';

const mutation = (over: Record<string, unknown> = {}) => ({
  mutate: vi.fn(), mutateAsync: vi.fn().mockResolvedValue(undefined), isPending: false, isError: false, ...over,
});

function state(data: unknown, over: Record<string, unknown> = {}) {
  return {
    household: { isLoading: false, isError: false, data, refetch: vi.fn() },
    join: mutation(), acceptInvite: mutation(), leave: mutation(), toggleShare: mutation(), ...over,
  };
}

const solo = { household_id: null, members: [], share_preferences: {} };
const shared = {
  household_id: 7,
  members: [{ id: 1, name: 'A'.repeat(80), email: 'long.address.that.keeps.going@example-domain-name.com' }],
  share_preferences: { goals: true },
};

describe('HouseholdPage', () => {
  beforeEach(async () => { await i18n.changeLanguage('en'); });

  it('has an h1, an invite CTA, and an empty state when solo', () => {
    useHousehold.mockReturnValue(state(solo));
    render(<HouseholdPage />);
    expect(screen.getByRole('heading', { level: 1, name: 'Household' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Invite someone' })).toBeInTheDocument();
    expect(screen.getByText('No household yet')).toBeInTheDocument();
  });

  it('invite CTA focuses the email field', async () => {
    useHousehold.mockReturnValue(state(solo));
    render(<HouseholdPage />);
    await userEvent.click(screen.getByRole('button', { name: 'Invite someone' }));
    expect(screen.getByLabelText('Invite by email')).toHaveFocus();
  });

  it('every sharing switch has an accessible name, and sharing is disabled while solo', () => {
    useHousehold.mockReturnValue(state(solo));
    render(<HouseholdPage />);
    const sw = screen.getAllByRole('switch');
    expect(sw).toHaveLength(4);
    expect(screen.getByRole('switch', { name: 'Share Goals with household' })).toBeDisabled();
    expect(screen.getByText('Join a household to turn sharing on.')).toBeInTheDocument();
  });

  it('toggling a switch calls the mutation; saved state reflected', async () => {
    const toggleShare = mutation();
    useHousehold.mockReturnValue(state(shared, { toggleShare }));
    render(<HouseholdPage />);
    expect(screen.getByRole('switch', { name: 'Share Goals with household' })).toBeChecked();
    await userEvent.click(screen.getByRole('switch', { name: 'Share Portfolio with household' }));
    expect(toggleShare.mutate).toHaveBeenCalledWith({ resourceType: 'portfolio', shared: true });
  });

  it('shows friendly errors, never raw server text', async () => {
    const join = mutation({ mutateAsync: vi.fn().mockRejectedValue(new Error('HTTP 500 user_not_found')) });
    useHousehold.mockReturnValue(state(solo, { join }));
    render(<HouseholdPage />);
    await userEvent.type(screen.getByLabelText('Invite by email'), 'x@y.com');
    await userEvent.click(screen.getByRole('button', { name: 'Send invitation' }));
    expect(await screen.findByRole('alert')).toHaveTextContent("We couldn't send the invitation");
    expect(screen.queryByText(/user_not_found/)).toBeNull();
  });

  it('load failure offers retry with plain copy', async () => {
    const refetch = vi.fn();
    useHousehold.mockReturnValue(state(undefined, { household: { isLoading: false, isError: true, data: undefined, refetch } }));
    render(<HouseholdPage />);
    expect(screen.getByText("We couldn't load your household")).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /retry|try again/i }));
    expect(refetch).toHaveBeenCalled();
  });

  it('Italian copy renders', async () => {
    await i18n.changeLanguage('it');
    useHousehold.mockReturnValue(state(solo));
    render(<HouseholdPage />);
    expect(screen.getByRole('heading', { level: 1, name: 'Famiglia' })).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Condividi Obiettivi con la famiglia' })).toBeInTheDocument();
  });
});
