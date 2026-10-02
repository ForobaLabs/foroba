import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../i18n';
import { PrivacyProvider, usePrivacy } from '../contexts/PrivacyContext';
import { KelenShell } from './KelenShell';

function setViewport(mobile: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: mobile && query.includes('max-width: 767px'),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

function PrivacyProbe() {
  const { isPrivate } = usePrivacy();
  return <span data-testid="probe">{String(isPrivate)}</span>;
}

function renderShell(path = '/goals', isAdmin = false) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={qc}>
        <PrivacyProvider>
          <MemoryRouter initialEntries={[path]}>
            <KelenShell isAdmin={isAdmin}>
              <h1>Page body</h1>
              <PrivacyProbe />
            </KelenShell>
          </MemoryRouter>
        </PrivacyProvider>
      </QueryClientProvider>
    </I18nextProvider>,
  );
}

beforeEach(() => {
  setViewport(false);
  void i18n.changeLanguage('en');
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('{}', { status: 401 }))));
});
afterEach(() => vi.unstubAllGlobals());

const nav = () => screen.getByRole('navigation', { name: /main navigation/i });

describe('KelenShell (desktop)', () => {
  it('marks the document as the kelen app', () => {
    renderShell();
    expect(document.querySelector('[data-app="kelen"]')).not.toBeNull();
  });

  it('groups navigation into the five planned groups', () => {
    renderShell();
    const groups = within(nav()).getAllByRole('group');
    expect(groups).toHaveLength(5);
    for (const name of ['Overview', 'Wealth', 'Plan', 'People', 'Build']) {
      expect(within(nav()).getByRole('group', { name })).toBeInTheDocument();
    }
  });

  it('lists the Admin entry for admins only', () => {
    const { unmount } = renderShell();
    expect(within(nav()).queryByRole('link', { name: 'Admin' })).toBeNull();
    unmount();
    renderShell('/goals', true);
    expect(within(nav()).getByRole('link', { name: 'Admin' })).toBeInTheDocument();
  });

  it('puts every destination inside a group', () => {
    renderShell('/', true);
    for (const label of [
      'Dashboard', 'Accounts', 'Portfolio', 'Markets', 'Goals', 'What-If',
      'Monthly report', 'Household', 'API & Webhooks', 'Jeli Lab', 'Admin',
    ]) {
      expect(within(nav()).getByRole('link', { name: label })).toBeInTheDocument();
    }
  });

  it('marks the current page with aria-current', () => {
    renderShell('/goals');
    expect(within(nav()).getByRole('link', { name: 'Goals' })).toHaveAttribute('aria-current', 'page');
    expect(within(nav()).getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current');
  });

  it('keeps account items out of the nav and inside the user menu', async () => {
    const user = userEvent.setup();
    renderShell();
    const labels = ['Profile', 'Security', 'Settings', 'Status', 'Legal', 'Help'];
    for (const label of labels) {
      expect(within(nav()).queryByRole('link', { name: label })).toBeNull();
    }
    await user.click(screen.getByRole('button', { name: /account menu/i }));
    const menu = screen.getByRole('dialog', { name: /account menu/i });
    for (const label of labels) {
      expect(within(menu).getByRole('link', { name: label })).toBeInTheDocument();
    }
    expect(within(menu).getByText(/your data stays on your server/i)).toBeInTheDocument();
  });

  it('toggles hidden amounts through the topbar button', async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(screen.getByRole('button', { name: /hide amounts/i }));
    expect(screen.getByTestId('probe')).toHaveTextContent('true');
    expect(screen.getByRole('button', { name: /show amounts/i })).toHaveAttribute('aria-pressed', 'true');
  });

  it('offers a language switcher in the user menu', async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(screen.getByRole('button', { name: /account menu/i }));
    await user.click(screen.getByRole('button', { name: 'IT' }));
    expect(i18n.language).toBe('it');
  });
});

describe('KelenShell (mobile)', () => {
  it('shows a bottom bar with Dashboard, Accounts, Goals and More, no sidebar', () => {
    setViewport(true);
    renderShell('/');
    const tabs = screen.getAllByRole('navigation').find((n) => within(n).queryByRole('button', { name: /more/i }));
    expect(tabs).toBeDefined();
    for (const label of ['Dashboard', 'Accounts', 'Goals']) {
      expect(within(tabs as HTMLElement).getByRole('link', { name: label })).toBeInTheDocument();
    }
    expect(screen.queryByRole('navigation', { name: /main navigation/i })).toBeNull();
  });
});

describe('KelenShell document title', () => {
  it.each([
    ['/', 'Dashboard'],
    ['/goals', 'Goals'],
    ['/whatif', 'What-If'],
    ['/reports/monthly', 'Monthly report'],
    ['/portfolio/yiriba/IE00B4L5Y983', 'Portfolio'],
    ['/security', 'Security'],
  ])("titles %s as '%s · Kelen by Foroba'", (path, label) => {
    renderShell(path);
    expect(document.title).toBe(`${label} · Kelen by Foroba`);
  });
});

describe('KelenShell Jeli panel', () => {
  it('has exactly one Jeli entry point', () => {
    renderShell();
    expect(screen.getAllByRole('button', { name: /jeli/i })).toHaveLength(1);
  });

  it('opens a complementary drawer, toggles aria-expanded and closes with Esc', async () => {
    const user = userEvent.setup();
    renderShell();
    const btn = screen.getByRole('button', { name: /jeli/i });
    expect(btn).toHaveAttribute('aria-expanded', 'false');
    await user.click(btn);
    expect(btn).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('complementary', { name: 'Jeli' })).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(btn).toHaveAttribute('aria-expanded', 'false');
  });

  it('explains a failure in plain language', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 500 }))));
    renderShell();
    await user.click(screen.getByRole('button', { name: /jeli/i }));
    await user.type(screen.getByRole('textbox', { name: /message for jeli/i }), 'hi');
    await user.click(screen.getByRole('button', { name: /^send$/i }));
    expect(await screen.findByText(/isn't available right now/i)).toBeInTheDocument();
  });
});
