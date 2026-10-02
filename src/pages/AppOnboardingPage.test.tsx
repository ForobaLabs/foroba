import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, expect, test, vi } from 'vitest';

type Done = (s: { language: string; theme: string }) => void;
const captured: { onComplete?: Done } = {};

vi.mock('@foroba/ui', async (orig) => {
  const actual = await orig<typeof import('@foroba/ui')>();
  return {
    ...actual,
    OnboardingPage: (props: { onComplete: Done }) => {
      captured.onComplete = props.onComplete;
      return <div>wizard</div>;
    },
  };
});
vi.mock('../auth/api', () => ({ completeOnboarding: vi.fn(async () => undefined) }));

import { AppOnboardingPage } from './AppOnboardingPage';

beforeEach(() => localStorage.clear());

// The shell reads language from foroba.profile (App.tsx) and theme from the useTheme store,
// so onboarding must write through those, not just raw localStorage keys.
test('chosen language and theme are saved where the app actually reads them', () => {
  render(<MemoryRouter><AppOnboardingPage /></MemoryRouter>);
  captured.onComplete?.({ language: 'it', theme: 'dark' });
  expect(JSON.parse(localStorage.getItem('foroba.profile') ?? '{}').language).toBe('it');
  expect(localStorage.getItem('foroba.theme')).toBe('dark');
  expect(localStorage.getItem('foroba.language')).toBe('it');
});
