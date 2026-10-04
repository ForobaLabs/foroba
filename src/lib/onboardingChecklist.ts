export type ChecklistId = 'email' | 'mfa' | 'import' | 'goal';

export interface ChecklistItem {
  id: ChecklistId;
  done: boolean;
  to: string;
}

export interface ChecklistInput {
  emailVerified: boolean;
  mfaEnabled: boolean;
  accountCount: number;
  goalCount: number;
}

export const CHECKLIST_DISMISS_KEY = 'foroba.checklist.dismissed';

export function buildChecklist(input: ChecklistInput): ChecklistItem[] {
  return [
    { id: 'email', done: input.emailVerified, to: '/profile' },
    { id: 'mfa', done: input.mfaEnabled, to: '/settings' },
    { id: 'import', done: input.accountCount > 0, to: '/accounts' },
    { id: 'goal', done: input.goalCount > 0, to: '/goals' },
  ];
}

export function isComplete(items: ChecklistItem[]): boolean {
  return items.every((i) => i.done);
}

export function isDismissed(): boolean {
  try {
    return localStorage.getItem(CHECKLIST_DISMISS_KEY) === 'true';
  } catch {
    return false;
  }
}

export function dismiss(): void {
  try {
    localStorage.setItem(CHECKLIST_DISMISS_KEY, 'true');
  } catch {
    // storage unavailable: the card simply reappears next visit
  }
}
