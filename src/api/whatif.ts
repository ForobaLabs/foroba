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
  includeDebts?: boolean;
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
  debtsEur?: number;
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
    include_debts: params.includeDebts ?? false,
  };
}

interface RawSimulationResult {
  points: Array<{ month: number; resolution: 'monthly' | 'quarterly' | 'yearly'; bank_eur: number; investments_eur: number; total_eur: number }>;
  goal_impacts: Array<{ goal_id: number; name: string; original_projected_completion: string | null; new_projection: { months_needed: number | null; projected_date: string | null } | null }>;
  degraded: boolean;
  disclaimer: string;
  debts_eur?: number;
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
    debtsEur: raw.debts_eur,
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

interface RawWhatIfParams {
  horizon_months: number;
  eliminate_categories?: string[] | null;
  reduce_merchant_pct?: Record<string, number> | null;
  income_delta_cents?: number;
  goal_contributions?: Array<{ goal_id: number; extra_monthly_cents: number }>;
  one_off_events?: Array<{ month_offset: number; amount_cents: number; label: string }>;
  investment_growth_rate_pct?: number;
  include_debts?: boolean;
}

function paramsFromApi(raw: RawWhatIfParams): WhatIfParams {
  return {
    horizonMonths: raw.horizon_months,
    eliminateCategories: raw.eliminate_categories ?? undefined,
    reduceMerchantPct: raw.reduce_merchant_pct ?? undefined,
    incomeDeltaCents: raw.income_delta_cents ?? 0,
    goalContributions: (raw.goal_contributions ?? []).map((g) => ({
      goalId: g.goal_id, extraMonthlyCents: g.extra_monthly_cents,
    })),
    oneOffEvents: (raw.one_off_events ?? []).map((e) => ({
      monthOffset: e.month_offset, amountCents: e.amount_cents, label: e.label,
    })),
    investmentGrowthRatePct: raw.investment_growth_rate_pct ?? 5.0,
    includeDebts: raw.include_debts ?? false,
  };
}

interface RawScenario {
  id: number; name: string; horizon_months: number; params: RawWhatIfParams;
  created_at: string; updated_at: string;
}

function scenarioFromApi(raw: RawScenario): WhatIfScenario {
  return {
    id: raw.id, name: raw.name, horizonMonths: raw.horizon_months,
    params: paramsFromApi(raw.params), createdAt: raw.created_at, updatedAt: raw.updated_at,
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
