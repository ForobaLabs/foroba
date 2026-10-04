import { describe, expect, it } from 'vitest';
import { visibleEvents } from './netWorthEvents';

const dates = ['2026-01-01', '2026-01-02', '2026-01-04'];
const ev = (date: string, label = 'f.csv') => ({ date, label, kind: 'import' as const });

describe('visibleEvents', () => {
  it('returns nothing for an empty series', () => {
    expect(visibleEvents([ev('2026-01-02')], [])).toEqual([]);
  });
  it('drops events outside the series range', () => {
    expect(visibleEvents([ev('2025-12-31'), ev('2026-01-05')], dates)).toEqual([]);
  });
  it('snaps a missing date to the next series date', () => {
    expect(visibleEvents([ev('2026-01-03')], dates)[0].x).toBe('2026-01-04');
  });
  it('collapses events on the same snapped date, keeping the latest', () => {
    const out = visibleEvents([ev('2026-01-03', 'a'), ev('2026-01-04', 'b')], dates);
    expect(out).toHaveLength(1);
    expect(out[0].label).toBe('b');
  });
});
