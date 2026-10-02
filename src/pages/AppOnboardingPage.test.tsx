import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, expect, test, vi } from 'vitest';
import i18n from '../i18n';

const completeOnboarding = vi.fn(async () => undefined);
vi.mock('../auth/api', () => ({ completeOnboarding: () => completeOnboarding() }));

import { AppOnboardingPage } from './AppOnboardingPage';

const setup = () =>
  render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={['/onboarding']}>
        <Routes>
          <Route path="/onboarding" element={<AppOnboardingPage />} />
          <Route path="/" element={<p>dashboard</p>} />
        </Routes>
      </MemoryRouter>
    </I18nextProvider>,
  );

beforeEach(async () => {
  localStorage.clear();
  completeOnboarding.mockClear();
  await i18n.changeLanguage('en');
});

test('reaches the dashboard in three clicks and marks onboarding done', async () => {
  const user = userEvent.setup();
  setup();
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/what stays private/i);
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/first account/i);
  await user.click(screen.getByRole('button', { name: 'Skip for now' }));
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/net worth/i);
  await user.click(screen.getByRole('button', { name: 'Go to my dashboard' }));
  expect(screen.getByText('dashboard')).toBeInTheDocument();
  expect(localStorage.getItem('foroba.onboarding.done')).toBe('1');
  expect(completeOnboarding).toHaveBeenCalledTimes(1);
});

test('progress indicator reports the current step', async () => {
  const user = userEvent.setup();
  setup();
  const bar = screen.getByRole('progressbar');
  expect(bar).toHaveAttribute('aria-valuenow', '1');
  expect(bar).toHaveAttribute('aria-valuemax', '3');
  expect(bar).toHaveAccessibleName('Step 1 of 3');
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '2');
});

test('Skip for now on the first step leaves straight for the dashboard', async () => {
  const user = userEvent.setup();
  setup();
  await user.click(screen.getByRole('button', { name: 'Skip for now' }));
  expect(screen.getByText('dashboard')).toBeInTheDocument();
  expect(localStorage.getItem('foroba.onboarding.done')).toBe('1');
});

// The shell reads language from foroba.profile (App.tsx) and theme from the useTheme store,
// so onboarding must write through those, not just raw localStorage keys.
test('chosen language and theme are saved where the app actually reads them', async () => {
  const user = userEvent.setup();
  setup();
  await user.selectOptions(screen.getByLabelText('Theme'), 'dark');
  await user.selectOptions(screen.getByLabelText('Language'), 'it');
  // Language switches the page copy immediately.
  await user.click(screen.getByRole('button', { name: 'Continua' }));
  await user.click(screen.getByRole('button', { name: 'Salta per ora' }));
  await user.click(screen.getByRole('button', { name: /dashboard/i }));
  expect(JSON.parse(localStorage.getItem('foroba.profile') ?? '{}').language).toBe('it');
  expect(localStorage.getItem('foroba.theme')).toBe('dark');
  expect(localStorage.getItem('foroba.language')).toBe('it');
});

test('the bank and portfolio hand-off links are reachable on step 2', async () => {
  const user = userEvent.setup();
  setup();
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByRole('link', { name: /bank account/i })).toHaveAttribute('href', expect.stringContaining('/handoff/pazuru'));
  expect(screen.getByRole('link', { name: /stocks, ETFs or crypto/i })).toHaveAttribute('href', expect.stringContaining('/handoff/tsumi'));
});

test('copy no longer claims data lives only on this device', () => {
  setup();
  expect(document.body.textContent).not.toMatch(/only on this device|never see/i);
});
