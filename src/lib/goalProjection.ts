/** Goal what-if projection. Mirrors backend/goal_share.py::project_series (monthly
 * compounding, integer cents, capped at MAX_MONTHS) so the sliders and the shared page agree. */

export const MAX_MONTHS = 360;
export const RATE_MAX_PCT = 8;

export interface GoalProjection {
  series: number[];
  monthsToTarget: number | null;
}

export function projectGoal(
  savedCents: number,
  targetCents: number,
  monthlyCents: number,
  ratePct: number,
): GoalProjection {
  const monthlyRate = ratePct / 100 / 12;
  let balance = savedCents;
  const series = [balance];
  let monthsToTarget: number | null = balance >= targetCents ? 0 : null;
  let month = 0;
  while (monthsToTarget === null && month < MAX_MONTHS) {
    balance = Math.round(balance * (1 + monthlyRate)) + monthlyCents;
    month += 1;
    series.push(balance);
    if (balance >= targetCents) monthsToTarget = month;
  }
  return { series, monthsToTarget };
}

/** Balance at a given month offset (clamped to the series, held flat after the cap). */
export function balanceAt(series: number[], month: number): number {
  return series[Math.min(Math.max(month, 0), series.length - 1)];
}

export function addMonths(from: Date, months: number): Date {
  const d = new Date(from.getFullYear(), from.getMonth() + months, 1);
  return d;
}
