import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '../i18n';
import { GoalWhatIf } from './GoalWhatIf';

const goal = { title: 'Trip', targetAmount: 3000, currentAmount: 1000, monthlyContribution: 500 };

afterEach(() => vi.restoreAllMocks());

describe('GoalWhatIf', () => {
  it('recomputes the summary when the monthly slider moves', () => {
    render(<GoalWhatIf goal={goal} currency="EUR" />);
    const before = screen.getByTestId('whatif-summary').textContent;
    fireEvent.change(screen.getAllByRole('slider')[0], { target: { value: '1000' } });
    expect(screen.getByTestId('whatif-summary').textContent).not.toBe(before);
  });

  it('flags a goal that is never reached', () => {
    render(<GoalWhatIf goal={{ ...goal, monthlyContribution: 0 }} currency="EUR" />);
    expect(screen.getByTestId('whatif-summary').textContent).toMatch(/isn't reached within 30 years/i);
  });

  it('creates a share link and shows it', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ token: 't', path: '/share/goal/t', expires_at: 1 }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    render(<GoalWhatIf goal={goal} currency="EUR" />);
    fireEvent.click(screen.getByRole('button', { name: /share/i }));
    await waitFor(() => expect(screen.getByTestId('share-url').textContent).toContain('/share/goal/t'));
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toMatchObject({ name: 'Trip', target_cents: 300000, saved_cents: 100000 });
    vi.unstubAllGlobals();
  });

  it('shows an error when sharing fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 500 })));
    render(<GoalWhatIf goal={goal} currency="EUR" />);
    fireEvent.click(screen.getByRole('button', { name: /share/i }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    vi.unstubAllGlobals();
  });
});
