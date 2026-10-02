// Sign-up intent carried from the Foroba Labs site (?app=&plan=). Client-only and
// advisory: it never grants a plan and is never sent to the server.
export type IntentApp = 'naforo' | 'yiriba' | 'kelen';
export type IntentPlan = 'free' | 'premium' | 'expert';
export interface SignupIntent { app: IntentApp; plan: IntentPlan }

const KEY = 'foroba.signupIntent';
const APPS: readonly IntentApp[] = ['naforo', 'yiriba', 'kelen'];
const PLANS: readonly IntentPlan[] = ['free', 'premium', 'expert'];
const HANDOFF: Record<IntentApp, string | null> = { naforo: 'pazuru', yiriba: 'tsumi', kelen: null };

const asApp = (v: unknown): IntentApp | null => (APPS as readonly unknown[]).includes(v) ? (v as IntentApp) : null;
const asPlan = (v: unknown): IntentPlan => (PLANS as readonly unknown[]).includes(v) ? (v as IntentPlan) : 'free';

export function parseIntent(search: string): SignupIntent | null {
  const q = new URLSearchParams(search);
  const app = asApp((q.get('app') ?? '').toLowerCase());
  if (!app) return null;
  return { app, plan: asPlan((q.get('plan') ?? '').toLowerCase()) };
}

export function saveIntent(i: SignupIntent): void {
  try { sessionStorage.setItem(KEY, JSON.stringify(i)); } catch { /* storage unavailable */ }
}

export function loadIntent(): SignupIntent | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const o = JSON.parse(raw) as { app?: unknown; plan?: unknown };
    const app = asApp(o.app);
    return app ? { app, plan: asPlan(o.plan) } : null;
  } catch { return null; }
}

export function clearIntent(): void {
  try { sessionStorage.removeItem(KEY); } catch { /* storage unavailable */ }
}

/** Same-origin Foroba endpoint that mints the cross-app handoff (Plan U). */
export function handoffHref(app: IntentApp): string | null {
  const target = HANDOFF[app];
  return target ? `/foroba-api/auth/handoff/${target}?redirect=/settings` : null;
}
