import { beforeEach, describe, expect, it } from 'vitest';
import { buildChecklist, dismiss, isComplete, isDismissed } from './onboardingChecklist';

const none = { emailVerified: false, mfaEnabled: false, accountCount: 0, goalCount: 0 };

describe('onboarding checklist', () => {
  beforeEach(() => { localStorage.clear(); });

  it('orders items email, mfa, import, goal', () => {
    expect(buildChecklist(none).map((i) => i.id)).toEqual(['email', 'mfa', 'import', 'goal']);
  });
  it('marks items done from the inputs', () => {
    const items = buildChecklist({ ...none, mfaEnabled: true, accountCount: 2 });
    expect(items.filter((i) => i.done).map((i) => i.id)).toEqual(['mfa', 'import']);
    expect(isComplete(items)).toBe(false);
  });
  it('is complete only when every item is done', () => {
    expect(isComplete(buildChecklist({ emailVerified: true, mfaEnabled: true, accountCount: 1, goalCount: 1 }))).toBe(true);
  });
  it('remembers dismissal', () => {
    expect(isDismissed()).toBe(false);
    dismiss();
    expect(isDismissed()).toBe(true);
  });
});
