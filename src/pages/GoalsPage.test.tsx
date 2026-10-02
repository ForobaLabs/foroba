import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../i18n';
import { GoalsPage } from './GoalsPage';

// In-memory stand-in for Foroba's /jeli/goals proxy (cents in, cents out, like Pazuru).
let store: Array<Record<string, unknown>> = [];
let nextId = 1;
function fakeGoalsApi(url: string, init?: RequestInit) {
  const json = (body: unknown) => Promise.resolve({ ok: true, json: async () => body } as Response);
  const m = /\/jeli\/goals\/?(\d+)?$/.exec(url);
  if (!m) return Promise.resolve({ ok: false } as Response);
  const method = init?.method ?? 'GET';
  if (method === 'POST') {
    const b = JSON.parse(String(init?.body));
    store.push({ id: nextId++, ...b, is_achieved: b.saved_cents >= b.target_cents });
    return json({});
  }
  if (method === 'PUT') {
    const b = JSON.parse(String(init?.body));
    store = store.map((g) => (String(g.id) === m[1] ? { ...g, ...b, is_achieved: b.saved_cents >= b.target_cents } : g));
    return json({});
  }
  if (method === 'DELETE') {
    store = store.filter((g) => String(g.id) !== m[1]);
    return json({});
  }
  return json({ goals: store, degraded: false });
}

const mount = () =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter><GoalsPage /></MemoryRouter>
    </QueryClientProvider>,
  );

describe('GoalsPage', () => {
  afterEach(() => vi.unstubAllGlobals());
  beforeEach(async () => {
    store = [];
    nextId = 1;
    vi.stubGlobal('fetch', vi.fn((u: string, i?: RequestInit) => fakeGoalsApi(u, i)));
    localStorage.clear();
    await i18n.changeLanguage('en');
  });

  it('shows h1, subtitle and an empty state with a create action; no fake savings badge', async () => {
    mount();
    expect(screen.getByRole('heading', { level: 1, name: 'Financial goals' })).toBeInTheDocument();
    expect(await screen.findByText('No goals yet')).toBeInTheDocument();
    expect(screen.queryByText(/18\s*%/)).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Create your first goal' }));
    expect(screen.getByLabelText('Title')).toBeInTheDocument();
  });

  it('shows human validation errors, focuses the first invalid field, and saves nothing', async () => {
    mount();
    await userEvent.click(screen.getByRole('button', { name: /New goal/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Save goal' }));
    expect(screen.getByLabelText('Title')).toHaveFocus();
    expect(screen.getByText('Give your goal a name')).toBeInTheDocument();
    expect(screen.getByText('Enter a number, for example 5000')).toBeInTheDocument();
    expect(screen.getByLabelText('Title')).toHaveAttribute('aria-invalid', 'true');
    expect(store).toHaveLength(0);
  });

  it('creates a goal with a long name, wraps it, and confirms before removing', async () => {
    mount();
    await userEvent.click(screen.getByRole('button', { name: /New goal/ }));
    const longName = 'Holiday fund '.repeat(9).trim(); // 116 chars
    await userEvent.type(screen.getByLabelText('Title'), longName);
    await userEvent.type(screen.getByLabelText(/Target amount/), '5000');
    await userEvent.click(screen.getByRole('button', { name: 'Save goal' }));
    expect(await screen.findByText(longName)).toBeInTheDocument();

    const done = screen.getByRole('button', { name: /Mark ".*" as done/ });
    expect(done).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: /^Remove ".*"/ }));
    const dialog = screen.getByRole('alertdialog');
    expect(within(dialog).getByText(/can't be undone/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Keep it' }));
    expect(screen.getByText(longName)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /^Remove ".*"/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Yes, remove' }));
    await vi.waitFor(() => expect(screen.queryByText(longName)).toBeNull());
    expect(await screen.findByText('No goals yet')).toBeInTheDocument();
  });

  it('accepts Italian decimals and rejects a title over the limit', async () => {
    await i18n.changeLanguage('it');
    mount();
    await userEvent.click(screen.getByRole('button', { name: /Nuovo obiettivo/ }));
    await userEvent.type(screen.getByLabelText('Titolo'), 'a');
    await userEvent.type(screen.getByLabelText(/Importo obiettivo/), '1.234,50');
    await userEvent.click(screen.getByRole('button', { name: 'Salva obiettivo' }));
    expect(screen.queryByText('Inserisci un numero, per esempio 5000')).toBeNull();
    expect(screen.getByRole('heading', { level: 1, name: 'Obiettivi finanziari' })).toBeInTheDocument();
  });

  it('keeps the form open and tells the user when saving fails', async () => {
    vi.stubGlobal('fetch', vi.fn((u: string, i?: RequestInit) =>
      i?.method === 'POST'
        ? Promise.resolve({ ok: false, status: 502, json: async () => ({}) } as Response)
        : fakeGoalsApi(u, i)));
    mount();
    await userEvent.click(screen.getByRole('button', { name: /New goal/ }));
    await userEvent.type(screen.getByLabelText('Title'), 'Trip');
    await userEvent.type(screen.getByLabelText(/Target amount/), '5000');
    await userEvent.click(screen.getByRole('button', { name: 'Save goal' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn't save/i);
    expect(screen.getByLabelText('Title')).toHaveValue('Trip');
  });
});
