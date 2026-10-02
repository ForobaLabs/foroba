import { describe, expect, it } from 'vitest';
import { GOAL_TITLE_MAX, validateGoal } from './validateGoal';

const ok = { title: 'Emergency fund', target: '5000', current: '', contribution: '', date: '' };
const TODAY = '2026-10-02';

describe('validateGoal', () => {
  it('accepts a minimal goal and defaults optionals to 0', () => {
    const r = validateGoal(ok, 'en', TODAY);
    expect(r.values).toEqual({ title: 'Emergency fund', target: 5000, current: 0, contribution: 0, date: undefined });
  });
  it('rejects empty and over-long titles at the boundary', () => {
    expect(validateGoal({ ...ok, title: '   ' }, 'en', TODAY).errors.title).toBe('titleRequired');
    expect(validateGoal({ ...ok, title: 'a'.repeat(GOAL_TITLE_MAX) }, 'en', TODAY).errors.title).toBeUndefined();
    expect(validateGoal({ ...ok, title: 'a'.repeat(GOAL_TITLE_MAX + 1) }, 'en', TODAY).errors.title).toBe('titleLong');
  });
  it.each([['abc', 'targetNaN'], ['', 'targetNaN'], ['0', 'targetMin'], ['-5', 'targetMin'], ['1000000001', 'amountMax']])(
    'target %s -> %s', (raw, key) => {
      expect(validateGoal({ ...ok, target: raw }, 'en', TODAY).errors.target).toBe(key);
    });
  it('accepts the 1e9 boundary', () => {
    expect(validateGoal({ ...ok, target: '1000000000' }, 'en', TODAY).values?.target).toBe(1e9);
  });
  it('parses locale decimals', () => {
    expect(validateGoal({ ...ok, target: '1.234,5' }, 'it', TODAY).values?.target).toBe(1234.5);
    expect(validateGoal({ ...ok, target: '1,234.5' }, 'en', TODAY).values?.target).toBe(1234.5);
  });
  it('rejects negative optional amounts and past dates', () => {
    expect(validateGoal({ ...ok, current: '-1' }, 'en', TODAY).errors.current).toBe('negative');
    expect(validateGoal({ ...ok, contribution: 'x' }, 'en', TODAY).errors.contribution).toBe('currentNaN');
    expect(validateGoal({ ...ok, date: TODAY }, 'en', TODAY).errors.date).toBe('dateInvalid');
    expect(validateGoal({ ...ok, date: '2026-10-03' }, 'en', TODAY).errors.date).toBeUndefined();
  });
  it('reports the first invalid field in form order', () => {
    const r = validateGoal({ title: '', target: 'x', current: '-1', contribution: '', date: '' }, 'en', TODAY);
    expect(r.firstInvalid).toBe('title');
    expect(r.values).toBeNull();
  });
});
