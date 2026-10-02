import { parseDecimal } from '../../lib/parseDecimal';

export const GOAL_TITLE_MAX = 120;
const AMOUNT_MAX = 1_000_000_000;

export type GoalField = 'title' | 'target' | 'current' | 'contribution' | 'date';
export type GoalErrorKey =
  | 'titleRequired' | 'titleLong' | 'targetNaN' | 'targetMin' | 'amountMax'
  | 'currentNaN' | 'negative' | 'dateInvalid';

export interface GoalInput { title: string; target: string; current: string; contribution: string; date: string }
export interface GoalValues { title: string; target: number; current: number; contribution: number; date?: string }

export interface GoalValidation {
  errors: Partial<Record<GoalField, GoalErrorKey>>;
  firstInvalid: GoalField | null;
  values: GoalValues | null;
}

const ORDER: GoalField[] = ['title', 'target', 'current', 'date', 'contribution'];

/** Validate the new-goal form. `today` is injectable for tests (YYYY-MM-DD). */
export function validateGoal(input: GoalInput, lang: string, today = new Date().toISOString().slice(0, 10)): GoalValidation {
  const errors: GoalValidation['errors'] = {};
  const title = input.title.trim();
  if (!title) errors.title = 'titleRequired';
  else if (title.length > GOAL_TITLE_MAX) errors.title = 'titleLong';

  const target = parseDecimal(input.target, lang);
  if (Number.isNaN(target)) errors.target = 'targetNaN';
  else if (target <= 0) errors.target = 'targetMin';
  else if (target > AMOUNT_MAX) errors.target = 'amountMax';

  // Optional numeric fields: empty means 0.
  const optional = (raw: string, field: 'current' | 'contribution'): number => {
    if (raw.trim() === '') return 0;
    const n = parseDecimal(raw, lang);
    if (Number.isNaN(n)) errors[field] = 'currentNaN';
    else if (n < 0) errors[field] = 'negative';
    else if (n > AMOUNT_MAX) errors[field] = 'amountMax';
    return n;
  };
  const current = optional(input.current, 'current');
  const contribution = optional(input.contribution, 'contribution');

  if (input.date && !(input.date > today)) errors.date = 'dateInvalid';

  const firstInvalid = ORDER.find((f) => errors[f]) ?? null;
  return {
    errors,
    firstInvalid,
    values: firstInvalid ? null : { title, target, current, contribution, date: input.date || undefined },
  };
}
