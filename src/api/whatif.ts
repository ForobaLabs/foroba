import { fetchJson } from './fetchJson';

const BASE = '/foroba-api/whatif';

export interface OneOffEvent { monthOffset: number; amountCents: number; label: string; }
export interface GoalContribution { goalId: number; extraMonthlyCents: number; }

export interface WhatIfParams {
  horizonMonths: number;
  eliminateCategories?: string[];
  reduceMerchantPct?: Record<string, number>;
  incomeDeltaCents?: number;
  goalContributions?: GoalContribution[];
  oneOffEvents?: OneOffEvent[];
  investmentGrowthRatePct?: number;
}

export interface ProjectionPoint {
  month: number;
  resolution: 'monthly' | 'quarterly' | 'yearly';
  bankEur: number;
  investmentsEur: number;
  totalEur: number;
}

export interface GoalImpact {
  goalId: number;
  name: string;
  originalProjectedCompletion: string | null;
  newProjection: { months_needed: number | null; projected_date: string | null } | null;
}

export interface SimulationResult {
  points: ProjectionPoint[];
  goalImpacts: GoalImpact[];
  degraded: boolean;
  disclaimer: string;
}

function toApiBody(params: WhatIfParams) {
  return {
    horizon_months: params.horizonMonths,
    eliminate_categories: params.eliminateCategories,
    reduce_merchant_pct: params.reduceMerchantPct,
    income_delta_cents: params.incomeDeltaCents ?? 0,
    goal_contributions: (params.goalContributions ?? []).map((g) => ({
      goal_id: g.goalId, extra_monthly_cents: g.extraMonthlyCents,
    })),
    one_off_events: (params.oneOffEvents ?? []).map((e) => ({
      month_offset: e.monthOffset, amount_cents: e.amountCents, label: e.label,
    })),
    investment_growth_rate_pct: params.investmentGrowthRatePct ?? 5.0,
  };
}

interface RawSimulationResult {
  points: Array<{ month: number; resolution: 'monthly' | 'quarterly' | 'yearly'; bank_eur: number; investments_eur: number; total_eur: number }>;
  goal_impacts: Array<{ goal_id: number; name: string; original_projected_completion: string | null; new_projection: { months_needed: number | null; projected_date: string | null } | null }>;
  degraded: boolean;
  disclaimer: string;
}

function fromApiResult(raw: RawSimulationResult): SimulationResult {
  return {
    points: raw.points.map((p) => ({
      month: p.month, resolution: p.resolution, bankEur: p.bank_eur,
      investmentsEur: p.investments_eur, totalEur: p.total_eur,
    })),
    goalImpacts: raw.goal_impacts.map((g) => ({
      goalId: g.goal_id, name: g.name,
      originalProjectedCompletion: g.original_projected_completion,
      newProjection: g.new_projection,
    })),
    degraded: raw.degraded,
    disclaimer: raw.disclaimer,
  };
}

export async function simulateWhatIf(params: WhatIfParams): Promise<SimulationResult> {
  const raw = await fetchJson<RawSimulationResult>(`${BASE}/simulate`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(toApiBody(params)),
    timeoutMs: 10000,
  });
  return fromApiResult(raw);
}

export interface WhatIfScenario {
  id: number;
  name: string;
  horizonMonths: number;
  params: WhatIfParams;
  createdAt: string;
  updatedAt: string;
}

interface RawScenario {
  id: number; name: string; horizon_months: number; params: Record<string, unknown>;
  created_at: string; updated_at: string;
}

function scenarioFromApi(raw: RawScenario): WhatIfScenario {
  return {
    id: raw.id, name: raw.name, horizonMonths: raw.horizon_months,
    params: raw.params as unknown as WhatIfParams, createdAt: raw.created_at, updatedAt: raw.updated_at,
  };
}

export async function listWhatIfScenarios(): Promise<WhatIfScenario[]> {
  const raw = await fetchJson<RawScenario[]>(`${BASE}/scenarios`, { credentials: 'include', timeoutMs: 5000 });
  return raw.map(scenarioFromApi);
}

export async function createWhatIfScenario(input: {
  name: string; horizonMonths: number; params: WhatIfParams;
}): Promise<WhatIfScenario> {
  const raw = await fetchJson<RawScenario>(`${BASE}/scenarios`, {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: input.name, horizon_months: input.horizonMonths, params: toApiBody(input.params) }),
    timeoutMs: 5000,
  });
  return scenarioFromApi(raw);
}

export async function getWhatIfScenario(id: number): Promise<WhatIfScenario & { projection: SimulationResult }> {
  const raw = await fetchJson<RawScenario & { projection: RawSimulationResult }>(`${BASE}/scenarios/${id}`, {
    credentials: 'include', timeoutMs: 10000,
  });
  return { ...scenarioFromApi(raw), projection: fromApiResult(raw.projection) };
}

export async function deleteWhatIfScenario(id: number): Promise<void> {
  await fetchJson<void>(`${BASE}/scenarios/${id}`, {
    method: 'DELETE', credentials: 'include', timeoutMs: 5000,
  }).catch(() => undefined); // 204 has no body; fetchJson's .json() call is swallowed here intentionally
}
