import { describe, expect, it } from 'vitest';
import { MAX_MONTHS, balanceAt, projectGoal } from './goalProjection';

describe('projectGoal (parity with backend goal_share.project_series)', () => {
  it('is linear without interest', () => {
    expect(projectGoal(100_000, 300_000, 50_000, 0)).toEqual({
      series: [100_000, 150_000, 200_000, 250_000, 300_000],
      monthsToTarget: 4,
    });
  });

  it('interest shortens the time to target', () => {
    const flat = projectGoal(100_000, 1_000_000, 50_000, 0).monthsToTarget!;
    const grown = projectGoal(100_000, 1_000_000, 50_000, 8).monthsToTarget!;
    expect(grown).toBeLessThan(flat);
  });

  it('handles reached and unreachable goals', () => {
    expect(projectGoal(500, 400, 0, 0)).toEqual({ series: [500], monthsToTarget: 0 });
    const p = projectGoal(0, 100, 0, 0);
    expect(p.monthsToTarget).toBeNull();
    expect(p.series).toHaveLength(MAX_MONTHS + 1);
  });

  it('balanceAt clamps to the series', () => {
    expect(balanceAt([1, 2, 3], 99)).toBe(3);
    expect(balanceAt([1, 2, 3], -4)).toBe(1);
  });
});
