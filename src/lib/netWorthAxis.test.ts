import { describe, expect, it } from 'vitest';
import { netWorthDomain, signedTick } from './netWorthAxis';

describe('signedTick', () => {
  it('prefixes negatives with a true minus sign and keeps the currency', () => {
    expect(signedTick(-1500, (v) => `€${Math.abs(v)}`)).toBe('−€1500');
  });
  it('leaves positives and zero unsigned', () => {
    expect(signedTick(2000, (v) => `€${v}`)).toBe('€2000');
    expect(signedTick(0, (v) => `€${v}`)).toBe('€0');
  });
});

describe('signedTick privacy', () => {
  it('does not leak the sign when amounts are masked', () => {
    expect(signedTick(-1500, () => '••••')).toBe('••••');
  });
});

describe('netWorthDomain', () => {
  it('pads min/max and always includes zero when the series crosses it', () => {
    const [lo, hi] = netWorthDomain([{ totalEur: -500 }, { totalEur: 9000 }]);
    expect(lo).toBeLessThan(-500);
    expect(hi).toBeGreaterThan(9000);
  });
  it('does not pin an all-positive series to zero', () => {
    const [lo] = netWorthDomain([{ totalEur: 40000 }, { totalEur: 41500 }]);
    expect(lo).toBeGreaterThan(0);
  });
  it('handles a flat series', () => {
    const [lo, hi] = netWorthDomain([{ totalEur: 100 }, { totalEur: 100 }]);
    expect(hi).toBeGreaterThan(lo);
  });
});
