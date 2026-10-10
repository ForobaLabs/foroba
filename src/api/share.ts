import { fetchJson } from './fetchJson';

const BASE = '/foroba-api/share';

export interface GoalShareInput {
  name: string;
  currency: string;
  savedCents: number;
  targetCents: number;
  monthlyCents: number;
  ratePct: number;
}

export interface SharedGoal {
  name: string;
  currency: string;
  saved_cents: number;
  target_cents: number;
  monthly_cents: number;
  rate_pct: number;
  series: number[];
  months_to_target: number | null;
  exp: number;
}

export async function createGoalShare(input: GoalShareInput): Promise<{ path: string; expiresAt: number }> {
  const raw = await fetchJson<{ path: string; expires_at: number }>(`${BASE}/goal`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: input.name,
      currency: input.currency,
      saved_cents: input.savedCents,
      target_cents: input.targetCents,
      monthly_cents: input.monthlyCents,
      rate_pct: input.ratePct,
    }),
    timeoutMs: 8000,
  });
  return { path: raw.path, expiresAt: raw.expires_at };
}

export function fetchSharedGoal(token: string): Promise<SharedGoal> {
  return fetchJson<SharedGoal>(`${BASE}/goal/${encodeURIComponent(token)}`, { timeoutMs: 8000 });
}
