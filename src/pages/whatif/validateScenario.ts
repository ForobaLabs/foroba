import { parseDecimal } from '../../lib/parseDecimal';

export type ScenarioField = 'amount' | 'years' | 'rate';

export interface ScenarioInput {
  amount: string;
  years: string;
  rate: string;
}

export interface ScenarioValues {
  amount: number;
  years: number;
  rate: number;
}

export interface ScenarioValidation {
  errors: Partial<Record<ScenarioField, MessageKey>>;
  /** First invalid field in form order, to focus it. */
  firstInvalid: ScenarioField | null;
  /** Present only when every field is valid. */
  values: ScenarioValues | null;
}

export const LIMITS = { maxAmount: 1_000_000, minYears: 1, maxYears: 60, minRate: -50, maxRate: 50 } as const;

/** English master copy; `errors` hold the keys, the page translates `whatif.errors.<key>`. */
export const MESSAGES = {
  amountNaN: 'Enter a number, for example 250',
  amountMin: 'Enter an amount greater than 0',
  amountMax: 'Enter an amount of 1,000,000 or less',
  years: 'Enter a whole number of years from 1 to 60',
  rate: 'Enter a yearly return between -50% and 50%',
} as const;

export type MessageKey = keyof typeof MESSAGES;

export function validateScenario(input: ScenarioInput, lang: string): ScenarioValidation {
  const errors: Partial<Record<ScenarioField, MessageKey>> = {};
  const amount = parseDecimal(input.amount, lang);
  const years = parseDecimal(input.years, lang);
  const rate = parseDecimal(input.rate, lang);

  if (Number.isNaN(amount)) errors.amount = 'amountNaN';
  else if (amount <= 0) errors.amount = 'amountMin';
  else if (amount > LIMITS.maxAmount) errors.amount = 'amountMax';

  if (!Number.isInteger(years) || years < LIMITS.minYears || years > LIMITS.maxYears) errors.years = 'years';

  if (Number.isNaN(rate) || rate < LIMITS.minRate || rate > LIMITS.maxRate) errors.rate = 'rate';

  const order: ScenarioField[] = ['amount', 'years', 'rate'];
  const firstInvalid = order.find((f) => errors[f]) ?? null;
  return { errors, firstInvalid, values: firstInvalid ? null : { amount, years, rate } };
}
