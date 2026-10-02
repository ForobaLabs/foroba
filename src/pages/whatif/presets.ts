import type { ScenarioInput } from './validateScenario';

export type PresetId = 'save' | 'debt' | 'invest';

/** One-tap starting points; they only prefill the three main inputs. */
export const PRESETS: Record<PresetId, ScenarioInput> = {
  save: { amount: '200', years: '10', rate: '2' },
  debt: { amount: '300', years: '3', rate: '0' },
  invest: { amount: '250', years: '20', rate: '7' },
};

export const DEFAULT_SCENARIO: ScenarioInput = { amount: '200', years: '10', rate: '5' };

export function activePreset(input: ScenarioInput): PresetId | null {
  const hit = (Object.entries(PRESETS) as Array<[PresetId, ScenarioInput]>).find(
    ([, p]) => p.amount === input.amount.trim() && p.years === input.years.trim() && p.rate === input.rate.trim(),
  );
  return hit ? hit[0] : null;
}
